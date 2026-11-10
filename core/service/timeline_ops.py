"""Timeline by time: read the project like the editor shows it and edit it by timestamp.

This is what lets Hermes say "at 01:23.500 change the text" against the SAME
document the open pane edits. Every function here is pure (document in,
document out); the service wraps them in the revision-checked journal write, so
manual edits are never overwritten: the ops are applied on the *current*
revision and the pane picks the new revision up on its next poll.

Times are seconds on the final timeline (transition overlaps already removed),
the same clock the pane's ``mm:ss.ms`` readout uses.
"""

from __future__ import annotations

import copy
import re
import secrets
from typing import Any, Callable

import project

EPS = 1e-6
MIN_SCENE = 0.1


class OpError(ValueError):
    """The edit cannot be applied; the message says why in plain words."""


def parse_time(value: Any) -> float:
    """``83.5``, ``"83,5"``, ``"1:23.5"`` or ``"01:23.500"`` -> seconds."""
    if isinstance(value, bool):
        raise OpError("tiempo inválido")
    if isinstance(value, (int, float)):
        if value < 0:
            raise OpError("el tiempo no puede ser negativo")
        return float(value)
    text = str(value or "").strip().replace(",", ".")
    parts = text.split(":")
    if not text or len(parts) > 3 or any(not re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise OpError(f"tiempo inválido: {value!r} (usa 83.5, 1:23.5 o 01:23.500)")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def fmt(seconds: float) -> str:
    total = int(round(max(0.0, seconds) * 1000))
    return f"{total // 60000:02d}:{(total % 60000) // 1000:02d}.{total % 1000:03d}"


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #


def _scenes(doc: dict) -> list[dict]:
    return [s for s in doc.get("scenes") or [] if isinstance(s, dict)]


def scene_spans(doc: dict) -> list[tuple[float, float]]:
    starts = project.scene_starts(doc)
    return [(starts[i], round(starts[i] + project.scene_duration(s), 6)) for i, s in enumerate(_scenes(doc))]


def _asset(doc: dict, asset_id: str | None) -> dict | None:
    return next((a for a in doc.get("assets") or [] if a.get("id") == asset_id), None)


def describe(
    doc: dict, asset_duration: Callable[[dict], float | None] | None = None
) -> dict:
    """The whole timeline as plain data (what ``GET /projects/<id>/timeline`` returns)."""
    spans = scene_spans(doc)
    scenes_out = []
    for index, (scene, (start, end)) in enumerate(zip(_scenes(doc), spans)):
        source = scene.get("source") or {}
        scenes_out.append({
            "number": index + 1,
            "id": scene.get("id"),
            "name": scene.get("name"),
            "start": start, "end": end, "duration": round(end - start, 3),
            "startTc": fmt(start), "endTc": fmt(end),
            "in": scene.get("in"), "out": scene.get("out"),
            "speed": project.scene_speed(scene),
            "transition": scene.get("transition", "none"),
            "volume": (scene.get("audio") or {}).get("volume", 100),
            "kind": source.get("kind"), "assetId": source.get("assetId"), "path": source.get("path"),
            "text": [
                {
                    "index": i, "content": t.get("content"),
                    "from": round(start + float(t.get("at") or 0), 3),
                    "to": round(start + float(t.get("until") if t.get("until") is not None else end - start), 3),
                    "position": t.get("position", "bottom"),
                }
                for i, t in enumerate(scene.get("text") or [])
            ],
        })
    events = []
    for ev in doc.get("audioEvents") or []:
        asset = _asset(doc, ev.get("assetId")) or {}
        length = asset_duration(asset) if asset_duration and asset else None
        at = float(ev.get("at") or 0)
        events.append({
            "id": ev.get("id"), "assetId": ev.get("assetId"), "path": asset.get("path"),
            "at": at, "atTc": fmt(at), "volume": ev.get("volume", 100),
            "duration": length, "end": round(at + length, 3) if length else None,
        })
    music = doc.get("music")
    return {
        "projectId": doc.get("projectId"), "revision": doc.get("revision"), "title": doc.get("title"),
        "duration": project.timeline_duration(doc), "durationTc": fmt(project.timeline_duration(doc)),
        "width": doc.get("width"), "height": doc.get("height"),
        "masterVolume": (doc.get("audio") or {}).get("masterVolume", 100),
        "scenes": scenes_out,
        "audioEvents": sorted(events, key=lambda e: e["at"]),
        "music": music if music else None,
        "assets": [
            {"id": a.get("id"), "kind": a.get("kind"), "path": a.get("path")} for a in doc.get("assets") or []
        ],
    }


def items_at(
    doc: dict, t: float, asset_duration: Callable[[dict], float | None] | None = None
) -> dict:
    """What is on screen / audible at time *t* (``GET /projects/<id>/at?t=``)."""
    full = describe(doc, asset_duration)
    active = [s for s in full["scenes"] if s["start"] - EPS <= t < s["end"] - EPS]
    if not active and full["scenes"] and abs(t - full["duration"]) < 1e-3:
        active = [full["scenes"][-1]]
    texts = [
        {"scene": s["number"], **x}
        for s in active for x in s["text"] if x["from"] - EPS <= t <= x["to"] + EPS
    ]
    sounds = [
        e for e in full["audioEvents"]
        if e["at"] - EPS <= t and (e["end"] is None or t < e["end"] + EPS) and (e["end"] is not None or t - e["at"] < 30)
    ]
    return {
        "time": t, "timeTc": fmt(t), "revision": full["revision"], "duration": full["duration"],
        "scenes": active, "text": texts, "audioEvents": sounds,
        "music": full["music"], "inRange": 0 <= t <= full["duration"] + 1e-3,
    }


# --------------------------------------------------------------------------- #
# editing
# --------------------------------------------------------------------------- #


def _resolve(doc: dict, op: dict) -> int:
    """Index of the scene an op talks about: ``scene`` (id, 1-based number, name) or ``time``."""
    scenes = _scenes(doc)
    if not scenes:
        raise OpError("el proyecto no tiene escenas")
    ref = op.get("scene")
    if ref is not None:
        if isinstance(ref, int) and not isinstance(ref, bool):
            if not 1 <= ref <= len(scenes):
                raise OpError(f"no existe la escena {ref} (hay {len(scenes)})")
            return ref - 1
        text = str(ref)
        for i, s in enumerate(scenes):
            if s.get("id") == text:
                return i
        if text.isdigit() and 1 <= int(text) <= len(scenes):
            return int(text) - 1
        for i, s in enumerate(scenes):
            if s.get("name") == text:
                return i
        raise OpError(f"escena desconocida: {text!r}")
    if op.get("time") is None and op.get("at") is None:
        raise OpError("indica la escena ('scene') o un tiempo ('time')")
    t = parse_time(op["time"] if op.get("time") is not None else op["at"])
    spans = scene_spans(doc)
    hit = None
    for i, (start, end) in enumerate(spans):
        if start - EPS <= t < end - EPS:
            hit = i  # later scene wins inside a crossfade
    if hit is None:
        if abs(t - spans[-1][1]) < 1e-3:
            return len(spans) - 1
        raise OpError(f"no hay escena en {fmt(t)} (el vídeo dura {fmt(spans[-1][1])})")
    return hit


def _num(op: dict, key: str, low: float, high: float) -> float:
    value = op.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            value = float(str(value).replace(",", "."))
        except ValueError:
            raise OpError(f"'{key}' debe ser un número") from None
    if not low <= float(value) <= high:
        raise OpError(f"'{key}' debe estar entre {low:g} y {high:g}")
    return float(value)


def _vol(op: dict) -> int:
    if op.get("mute"):
        return 0
    return int(round(_num(op, "volume", 0, 100)))


def _new_id(prefix: str) -> str:
    return prefix + secrets.token_hex(4)


def apply_op(doc: dict, op: dict) -> str:
    """Apply one op in place; return a one-line Spanish summary."""
    if not isinstance(op, dict) or not isinstance(op.get("op"), str):
        raise OpError("cada operación necesita 'op'")
    kind = op["op"]
    scenes = doc.setdefault("scenes", [])

    if kind == "set_text":
        i = _resolve(doc, op)
        scene = scenes[i]
        start, end = scene_spans(doc)[i]
        content = str(op.get("content", "")).strip()
        items = list(scene.get("text") or [])
        index = int(op.get("index", 0))
        by_time = op.get("scene") is None and op.get("index") is None
        if by_time and not op.get("add") and items:
            # "at 3:13 change the text": replace the caption that is ON SCREEN at that moment;
            # if none is, this becomes a new caption that starts at that moment.
            t = parse_time(op["time"] if op.get("time") is not None else op["at"])
            active = [k for k, x in enumerate(items)
                      if start + float(x.get("at") or 0) - EPS <= t <= start + float(x.get("until", end - start)) + EPS]
            if active:
                index = active[0]
            else:
                op = dict(op, add=True)
                if op.get("from") is None:
                    op["from"] = t
        if not content:
            if index < len(items):
                items.pop(index)
            scene["text"] = items
            return f"escena {i + 1}: texto quitado"
        item = dict(items[index]) if index < len(items) and not op.get("add") else {}
        item["content"] = content[: project.MAX_TEXT_LENGTH]
        local_from = parse_time(op["from"]) - start if op.get("from") is not None else item.get("at", 0)
        local_to = parse_time(op["to"]) - start if op.get("to") is not None else item.get("until", end - start)
        item["at"] = round(max(0.0, float(local_from)), 3)
        item["until"] = round(min(end - start, max(item["at"] + 0.1, float(local_to))), 3)
        item.setdefault("position", "bottom")
        for key in ("position", "size", "color", "border", "borderColor", "shadow", "animation"):
            if key in op:
                item[key] = op[key]
        if op.get("add") or index >= len(items):
            items.append(item)
        else:
            items[index] = item
        scene["text"] = items
        return f"escena {i + 1}: texto «{item['content'][:40]}» de {fmt(start + item['at'])} a {fmt(start + item['until'])}"

    if kind == "trim":
        i = _resolve(doc, op)
        scene = scenes[i]
        speed = project.scene_speed(scene)
        if op.get("in") is not None:
            scene["in"] = round(_num(op, "in", 0, 86400), 3)
        if op.get("out") is not None:
            scene["out"] = round(_num(op, "out", 0, 86400), 3)
        if op.get("duration") is not None:
            scene["out"] = round(float(scene["in"]) + _num(op, "duration", MIN_SCENE, 86400) * speed, 3)
        if float(scene["out"]) - float(scene["in"]) < MIN_SCENE:
            raise OpError("la escena quedaría de menos de 0,1 s")
        return f"escena {i + 1}: recortada a {scene['in']}–{scene['out']} s de la fuente"

    if kind == "split":
        i = _resolve(doc, op)
        scene = scenes[i]
        start, end = scene_spans(doc)[i]
        t = parse_time(op["time"] if op.get("time") is not None else op["at"])
        if not (start + MIN_SCENE <= t <= end - MIN_SCENE):
            raise OpError(f"{fmt(t)} está demasiado cerca del borde de la escena {i + 1} ({fmt(start)}–{fmt(end)})")
        speed = project.scene_speed(scene)
        cut = round(float(scene["in"]) + (t - start) * speed, 3)
        second = copy.deepcopy(scene)
        second["id"] = _new_id("sc_")
        second["in"] = cut
        second["transition"] = "none"
        second["text"] = []
        scene["out"] = cut
        scene["text"] = [dict(x, until=min(float(x.get("until", 1e9)), t - start)) for x in scene.get("text") or [] if float(x.get("at") or 0) < t - start - 0.05]
        scenes.insert(i + 1, second)
        return f"escena {i + 1} partida en {fmt(t)}"

    if kind == "delete_scene":
        i = _resolve(doc, op)
        gone = scenes.pop(i)
        return f"escena {i + 1} ({gone.get('name') or gone.get('id')}) eliminada"

    if kind == "move_scene":
        i = _resolve(doc, op)
        if op.get("to_index") is not None:
            dest = int(_num(op, "to_index", 1, max(1, len(scenes)))) - 1
        elif op.get("to_time") is not None:
            t = parse_time(op["to_time"])
            starts = project.scene_starts(doc)
            dest = next((k for k, s in enumerate(starts) if s >= t - EPS), len(scenes) - 1)
        else:
            raise OpError("move_scene necesita 'to_index' (1-based) o 'to_time'")
        scene = scenes.pop(i)
        scenes.insert(dest, scene)
        return f"escena {i + 1} movida a la posición {dest + 1}"

    if kind == "set_transition":
        i = _resolve(doc, op)
        value = op.get("value", "none")
        project.transition_parts(value)  # raises ProjectError on junk
        scenes[i]["transition"] = value
        return f"escena {i + 1}: transición {value}"

    if kind == "set_speed":
        i = _resolve(doc, op)
        scenes[i]["speed"] = round(_num(op, "speed", 0.5, 2.0), 3)
        return f"escena {i + 1}: velocidad {scenes[i]['speed']}x"

    if kind == "set_volume":
        target = op.get("target", "scene")
        volume = _vol(op)
        if target == "scene":
            i = _resolve(doc, op)
            scenes[i]["audio"] = {**(scenes[i].get("audio") or {}), "volume": volume}
            return f"escena {i + 1}: volumen {volume}%"
        if target == "music":
            if not doc.get("music"):
                raise OpError("el proyecto no tiene música")
            doc["music"]["volume"] = volume
            return f"música: volumen {volume}%"
        if target == "master":
            doc["audio"] = {**(doc.get("audio") or {}), "masterVolume": volume}
            return f"volumen general {volume}%"
        if target in ("event", "audio"):
            ev = _event(doc, op)
            ev["volume"] = volume
            return f"sonido {ev['id']}: volumen {volume}%"
        raise OpError("target debe ser scene, music, master o event")

    if kind == "add_audio":
        asset = _asset(doc, op.get("assetId"))
        if asset is None or asset.get("kind") != "audio":
            raise OpError("assetId debe ser un audio del proyecto (mira 'assets' en /timeline)")
        at = parse_time(op.get("at", 0))
        ev = {"id": _new_id("ae_"), "assetId": asset["id"], "at": round(at, 3), "volume": _vol({"volume": op.get("volume", 80)})}
        for key in ("fadeIn", "fadeOut"):
            if op.get(key) is not None:
                ev[key] = round(_num(op, key, 0, 30), 3)
        doc["audioEvents"] = list(doc.get("audioEvents") or []) + [ev]
        return f"sonido {ev['id']} añadido en {fmt(at)}"

    if kind in ("move_audio", "set_audio"):
        ev = _event(doc, op)
        if op.get("at") is not None:
            ev["at"] = round(parse_time(op["at"]), 3)
        if op.get("volume") is not None or op.get("mute"):
            ev["volume"] = _vol(op)
        if op.get("assetId"):
            asset = _asset(doc, op["assetId"])
            if asset is None or asset.get("kind") != "audio":
                raise OpError("assetId debe ser un audio del proyecto")
            ev["assetId"] = asset["id"]
        return f"sonido {ev['id']}: ahora en {fmt(ev['at'])}, volumen {ev.get('volume', 100)}%"

    if kind == "remove_audio":
        ev = _event(doc, op)
        doc["audioEvents"] = [e for e in doc["audioEvents"] if e is not ev]
        if not doc["audioEvents"]:
            del doc["audioEvents"]
        return f"sonido {ev['id']} quitado"

    if kind == "set_music":
        music = dict(doc.get("music") or {})
        if op.get("assetId"):
            asset = _asset(doc, op["assetId"])
            if asset is None or asset.get("kind") != "audio":
                raise OpError("assetId debe ser un audio del proyecto")
            music["assetId"] = asset["id"]
        if not music.get("assetId"):
            raise OpError("indica assetId para la música")
        music.setdefault("volume", 50)
        for key in ("volume",):
            if op.get(key) is not None:
                music[key] = int(round(_num(op, key, 0, 100)))
        for key in ("fadeIn", "fadeOut"):
            if op.get(key) is not None:
                music[key] = round(_num(op, key, 0, 10), 3)
        for key in ("loop", "ducking"):
            if op.get(key) is not None:
                music[key] = bool(op[key])
        doc["music"] = music
        return "música actualizada"

    if kind == "remove_music":
        doc.pop("music", None)
        return "música quitada"

    if kind == "set_title":
        doc["title"] = str(op.get("title", "")).strip()[:120] or doc.get("title")
        return f"título: {doc['title']}"

    raise OpError(f"operación desconocida: {kind!r}")


def _event(doc: dict, op: dict) -> dict:
    ident = op.get("id") or op.get("event")
    if ident is None and op.get("time") is not None:
        t = parse_time(op["time"])
        near = sorted(doc.get("audioEvents") or [], key=lambda e: abs(float(e.get("at") or 0) - t))
        if near:
            return near[0]
    for ev in doc.get("audioEvents") or []:
        if ev.get("id") == ident:
            return ev
    raise OpError(f"sonido desconocido: {ident!r} (mira 'audioEvents' en /timeline)")


def _fit_text(doc: dict, summary: list[str]) -> None:
    """After a trim/speed/split, keep captions inside their scene (clamp, or drop if they no longer fit)."""
    for number, scene in enumerate(_scenes(doc), start=1):
        length = project.scene_duration(scene)
        kept = []
        for item in scene.get("text") or []:
            at = float(item.get("at") or 0)
            until = item.get("until")
            if at >= length - 0.05:
                summary.append(f"aviso: el texto «{str(item.get('content'))[:30]}» de la escena {number} quedó fuera y se quitó")
                continue
            if until is not None and float(until) > length:
                item = dict(item, until=round(length, 3))
            kept.append(item)
        if kept != (scene.get("text") or []):
            scene["text"] = kept


def apply_ops(doc: dict, ops: list) -> tuple[dict, list[str]]:
    if not isinstance(ops, list) or not ops:
        raise OpError("'ops' debe ser una lista con al menos una operación")
    if len(ops) > 100:
        raise OpError("máximo 100 operaciones por llamada")
    work = copy.deepcopy(doc)
    summary: list[str] = []
    for number, op in enumerate(ops, start=1):
        try:
            summary.append(apply_op(work, op))
            _fit_text(work, summary)
        except project.ProjectError as exc:
            raise OpError(f"operación {number}: {exc}") from exc
        except OpError as exc:
            raise OpError(f"operación {number}: {exc}") from exc
    return work, summary