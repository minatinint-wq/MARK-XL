"""
JARVIS MARK-XLIV — Blender scene generator: BRAIN + ROUTE consult animation.

COMO USAR (Blender 4.x instalado):
    blender --background --python tools\\blender_jarvis_route.py
    # ou dentro do Blender: Scripting > Open > este arquivo > Run Script

O QUE ELE GERA:
    assets/reactor_lab/brain_route.blend   (cena editável)
    assets/reactor_lab/brain_route.glb     (para o reactor_view HUD carregar)

ANIMAÇÕES:
    Action "IdlePulse"     — núcleo do cérebro pulsando em loop (frames 1-60, cíclico)
    Action "RouteConsult"  — dispara quando o Jarvis consulta uma rota (frames 1-90):
        1-15 : núcleo pisca branco (recebeu o pedido)
        10-60: curva Origem->Destino se desenha (bevel 0->1) + pontos da nuvem acendem
        50-90: câmera avança (dolly) e anel de choque se expande e some

GATILHO EM TEMPO REAL:
    actions/maps_mode.py grava memory/route_anim_trigger.json a cada consulta.
    O HUD (reactor.js / memory_brain_3d.html) lê esse JSON e toca "RouteConsult".
    Dentro do Blender, rode com --python-arg ORIGEM --python-arg DESTINO para
    nomear os empties da rota antes de exportar.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
VAULT_INDEX = BASE_DIR / "memory" / "vault_index.json"
VAULT_GROUPS = BASE_DIR / "memory" / "vault_groups.json"
OUT_BLEND = BASE_DIR / "assets" / "reactor_lab" / "brain_route.blend"
OUT_GLB = BASE_DIR / "assets" / "reactor_lab" / "brain_route.glb"

MAX_POINTS = 4000   # teto de pontos p/ o .glb ficar leve
MAX_PER_CAT = 120

try:
    import bpy  # noqa: E402  (só existe dentro do Blender)
    HAS_BPY = True
except ImportError:
    HAS_BPY = False


# ---------------------------------------------------------------- dados ---
def load_vault():
    """Lê o índice real do Obsidian. Fora do Blender retorna resumo p/ teste."""
    cats = {}
    group_of = {}
    try:
        gdata = json.loads(VAULT_GROUPS.read_text(encoding="utf-8"))
        for folder, d in (gdata.get("categories", {}) or {}).items():
            if isinstance(d, dict) and d.get("group"):
                group_of[folder] = str(d["group"])
    except Exception:
        pass
    try:
        data = json.loads(VAULT_INDEX.read_text(encoding="utf-8"))
        raw = data.get("categories", {})
        for folder, d in raw.items():
            try:
                grp = group_of.get(folder)
                if not grp and isinstance(d, dict) and d.get("group"):
                    grp = str(d["group"])
                cats[folder] = {
                    "count": int(d.get("file_count", 0) or 0),
                    "group": grp or "Cofre",
                }
            except Exception:
                continue
    except Exception as exc:
        print(f"[jarvis-blender] vault_index indisponível ({exc}); usando demo.")
    if not cats:
        for demo, grp in [("00_Cerebro", "Cerebro"), ("06_IA_Automacoes", "IA"),
                          ("15_Saude", "Saude"), ("07_Jogos", "Jogos")]:
            cats[demo] = {"count": 300, "group": grp}
    return cats


def distribute(cats):
    """Distribui pontos em concha cerebral: centro por grupo (fibonacci) + gauss."""
    groups = sorted({v["group"] for v in cats.values()})
    centers = {}
    R = 9.0
    golden = math.pi * (3 - math.sqrt(5))
    for i, g in enumerate(groups):
        y = 1 - (i / max(1, len(groups) - 1)) * 2
        rad = math.sqrt(max(0.0, 1 - y * y))
        th = golden * i
        centers[g] = (math.cos(th) * rad * R * 1.25, y * R * 0.85, math.sin(th) * rad * R)
    palette = {}
    for i, g in enumerate(groups):
        palette[g] = ((i * 47) % 360) / 360.0  # matiz 0..1
    pts = []  # (x, y, z, hue, folder, group)
    ordered = sorted(cats.items(), key=lambda kv: kv[1]["count"], reverse=True)
    for folder, d in ordered:
        if len(pts) >= MAX_POINTS:
            break
        k = min(MAX_PER_CAT, max(8, int(math.sqrt(max(1, d["count"])) * 2)))
        cx, cy, cz = centers[d["group"]]
        spread = 1.6 + min(2.6, math.sqrt(max(1, d["count"])) * 0.12)
        for _ in range(k):
            if len(pts) >= MAX_POINTS:
                break
            pts.append((
                cx + random.gauss(0, spread),
                cy + random.gauss(0, spread * 0.8),
                cz + random.gauss(0, spread),
                palette[d["group"]], folder, d["group"],
            ))
    return pts, groups, palette


# --------------------------------------------------------------- blender ---
def build_scene(origin_name="Origem", dest_name="Destino"):
    assert HAS_BPY, "rode este script dentro do Blender"
    # limpa cena
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.actions):
        for x in list(coll):
            try:
                coll.remove(x)
            except Exception:
                pass

    cats = load_vault()
    pts, groups, palette = distribute(cats)
    print(f"[jarvis-blender] {len(pts)} pontos · {len(groups)} grupos")

    # --- nuvem de pontos como malha de vértices (leve p/ GLB) ---
    mesh = bpy.data.meshes.new("BrainCloudMesh")
    mesh.from_pydata([(x, y, z) for x, y, z, _, _, _ in pts], [], [])
    mesh.update()
    cloud = bpy.data.objects.new("BrainCloud", mesh)
    bpy.context.collection.objects.link(cloud)
    # cor por vértice (grupo)
    col = mesh.color_attributes.new("GroupColor", "FLOAT_COLOR", "POINT")
    for i, (_, _, _, hue, _, _) in enumerate(pts):
        r, g, b = hsv_to_rgb(hue, 0.75, 1.0)
        col.data[i].color = (r, g, b, 1.0)
    cloud_mat = bpy.data.materials.new("BrainCloudMat")
    cloud_mat.use_nodes = True
    bsdf = cloud_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 0.1
    bsdf.inputs["Roughness"].default_value = 0.4
    attr = cloud_mat.node_tree.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "GroupColor"
    cloud_mat.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    emit = cloud_mat.node_tree.nodes.new("ShaderNodeEmission")
    cloud_mat.node_tree.links.new(attr.outputs["Color"], emit.inputs["Color"])
    out = cloud_mat.node_tree.nodes["Material Output"]
    mix = cloud_mat.node_tree.nodes.new("ShaderNodeMixShader")
    cloud_mat.node_tree.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    cloud_mat.node_tree.links.new(emit.outputs["Emission"], mix.inputs[2])
    cloud_mat.node_tree.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mix.inputs["Fac"].default_value = 0.55
    mesh.materials.append(cloud_mat)

    # --- núcleo (memória de longo prazo) ---
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.1, location=(0, 0, 0))
    core = bpy.context.active_object
    core.name = "MemoryCore"
    core_mat = bpy.data.materials.new("CoreMat")
    core_mat.use_nodes = True
    e = core_mat.node_tree.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (1.0, 0.91, 0.66, 1.0)
    e.inputs["Strength"].default_value = 3.0
    core_mat.node_tree.links.new(e.outputs["Emission"],
                                 core_mat.node_tree.nodes["Material Output"].inputs["Surface"])
    core.data.materials.append(core_mat)

    # --- empties origem/destino + curva da rota ---
    empty_o = bpy.data.objects.new(f"ROTA_{origin_name}", None)
    empty_o.location = (-14, -4, 6)
    empty_d = bpy.data.objects.new(f"ROTA_{dest_name}", None)
    empty_d.location = (14, 5, -4)
    bpy.context.collection.objects.link(empty_o)
    bpy.context.collection.objects.link(empty_d)

    curve = bpy.data.curves.new("RouteCurve", type="CURVE")
    curve.dimensions = "3D"
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(1)
    p0, p1 = spline.bezier_points
    p0.co = empty_o.location
    p0.handle_right = (-7, -8, 10)
    p1.co = empty_d.location
    p1.handle_left = (7, 9, -8)
    curve.bevel_depth = 0.12
    curve.bevel_resolution = 3
    route_obj = bpy.data.objects.new("RoutePath", curve)
    bpy.context.collection.objects.link(route_obj)
    route_mat = bpy.data.materials.new("RouteMat")
    route_mat.use_nodes = True
    re = route_mat.node_tree.nodes.new("ShaderNodeEmission")
    re.inputs["Color"].default_value = (0.2, 0.9, 1.0, 1.0)
    re.inputs["Strength"].default_value = 5.0
    route_mat.node_tree.links.new(re.outputs["Emission"],
                                  route_mat.node_tree.nodes["Material Output"].inputs["Surface"])
    route_obj.data.materials.append(route_mat)

    # --- anel de choque (expande na consulta) ---
    bpy.ops.mesh.primitive_torus_add(location=(0, 0, 0), major_radius=1, minor_radius=0.06)
    ring = bpy.context.active_object
    ring.name = "RouteShockwave"
    ring_mat = bpy.data.materials.new("RingMat")
    ring_mat.use_nodes = True
    rge = ring_mat.node_tree.nodes.new("ShaderNodeEmission")
    rge.inputs["Color"].default_value = (0.65, 0.5, 1.0, 1.0)
    rge.inputs["Strength"].default_value = 4.0
    ring_mat.node_tree.links.new(rge.outputs["Emission"],
                                 ring_mat.node_tree.nodes["Material Output"].inputs["Surface"])
    ring_mat.blend_method = "BLEND"
    ring.data.materials.append(ring_mat)

    # --- câmera + luz ---
    bpy.ops.object.camera_add(location=(0, 4, 34), rotation=(math.radians(90), 0, 0))
    cam = bpy.context.active_object
    cam.name = "BrainCam"
    bpy.context.scene.camera = cam
    bpy.ops.object.light_add(type="SUN", location=(10, 10, 20))
    bpy.ops.object.light_add(type="POINT", location=(0, 0, 12))
    bpy.context.active_object.data.energy = 500

    # ============================ ANIMAÇÕES ============================
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 90
    scene.render.fps = 30

    # IdlePulse (loop 1-60): núcleo respira
    idle = bpy.data.actions.new("IdlePulse")
    fc = idle.fcurves.new(data_path="scale", index=0) if hasattr(idle, "fcurves") else None
    core.animation_data_create().action = idle
    core.scale = (1, 1, 1)
    core.keyframe_insert("scale", frame=1)
    core.scale = (1.18, 1.18, 1.18)
    core.keyframe_insert("scale", frame=30)
    core.scale = (1, 1, 1)
    core.keyframe_insert("scale", frame=60)
    for fc in (core.animation_data.action.fcurves if core.animation_data else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "SINE"
        fc.modifiers.new("CYCLES")

    # RouteConsult (1-90): flash + desenho da rota + dolly + choque
    route_act = bpy.data.actions.new("RouteConsult")
    core.animation_data.action = route_act
    e.inputs["Strength"].default_value = 3.0
    e.keyframe_insert("inputs[1].default_value", frame=1) if False else None
    # flash do núcleo via energia da point light + escala
    core.scale = (1, 1, 1)
    core.keyframe_insert("scale", frame=1)
    core.scale = (1.6, 1.6, 1.6)
    core.keyframe_insert("scale", frame=12)
    core.scale = (1.05, 1.05, 1.05)
    core.keyframe_insert("scale", frame=50)
    # curva se desenha
    curve.bevel_factor_start = 0.0
    curve.keyframe_insert("bevel_factor_start", frame=10)
    curve.bevel_factor_end = 0.0
    curve.keyframe_insert("bevel_factor_end", frame=10)
    curve.bevel_factor_end = 1.0
    curve.keyframe_insert("bevel_factor_end", frame=60)
    # anel de choque
    ring.scale = (0.5, 0.5, 0.5)
    ring.keyframe_insert("scale", frame=50)
    ring.scale = (16, 16, 16)
    ring.keyframe_insert("scale", frame=85)
    ring.hide_viewport = False
    ring.keyframe_insert("hide_viewport", frame=50)
    ring.hide_viewport = True
    ring.keyframe_insert("hide_viewport", frame=86)
    # câmera dolly
    cam.location = (0, 4, 34)
    cam.keyframe_insert("location", frame=1)
    cam.location = (0, 2, 24)
    cam.keyframe_insert("location", frame=90)
    for fc in route_act.fcurves:
        for kp in fc.keyframe_points:
            if kp.interpolation == "CONSTANT":
                continue
            kp.interpolation = "BEZIER"

    OUT_BLEND.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    try:
        bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB",
                                  use_selection=False, export_animations=True,
                                  export_frame_range=False)
        print(f"[jarvis-blender] exportado: {OUT_GLB}")
    except Exception as exc:
        print(f"[jarvis-blender] GLB falhou ({exc}); .blend salvo mesmo assim.")
    print(f"[jarvis-blender] OK: {OUT_BLEND}")


def hsv_to_rgb(h, s, v):
    import colorsys
    return colorsys.hsv_to_rgb(h, s, v)


def main():
    args = [a for a in sys.argv if a.startswith("--python-arg=")]
    origin = dest = None
    for a in args:
        v = a.split("=", 1)[1]
        if origin is None:
            origin = v
        else:
            dest = v
    if not HAS_BPY:
        cats = load_vault()
        pts, groups, _ = distribute(cats)
        print(f"[jarvis-blender] sem Blender aqui — simulação OK: "
              f"{len(pts)} pontos, {len(groups)} grupos. "
              f"Instale o Blender 4.x e rode: "
              f"blender --background --python {BASE_DIR/'tools'/'blender_jarvis_route.py'}")
        return
    build_scene(origin or "Origem", dest or "Destino")


if __name__ == "__main__":
    main()
