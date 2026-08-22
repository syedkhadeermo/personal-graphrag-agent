import hashlib
import json
import math
import os
import shutil

import bpy
from mathutils import Vector


RESULT_DIRECTORY = r"C:\AI_Worker\results\cad_flow_channel"
FREECAD_MANIFEST = os.path.join(
    RESULT_DIRECTORY,
    "flow_channel_manifest.json",
)
OPENFOAM_SUMMARY = os.path.join(
    RESULT_DIRECTORY,
    "openfoam_summary.json",
)
BLEND_PATH = os.path.join(
    RESULT_DIRECTORY,
    "flow_channel_animation.blend",
)
VIDEO_PATH = os.path.join(
    RESULT_DIRECTORY,
    "flow_channel_animation.mp4",
)
FRAME_DIRECTORY = os.path.join(
    RESULT_DIRECTORY,
    "animation_frames",
)
PREVIEW_PATH = os.path.join(
    RESULT_DIRECTORY,
    "flow_channel_preview.png",
)
FINAL_MANIFEST = os.path.join(
    RESULT_DIRECTORY,
    "workflow_manifest.json",
)


def load_json(path: str) -> dict:
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as source_file:
        return json.load(source_file)


def sha256(path: str) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as source_file:
        for block in iter(
            lambda: source_file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def clear_scene() -> None:
    bpy.ops.object.select_all(
        action="SELECT"
    )
    bpy.ops.object.delete(
        use_global=False
    )

    for data_collection in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for data_block in list(
            data_collection
        ):
            if data_block.users == 0:
                data_collection.remove(
                    data_block
                )


def material(
    name: str,
    color: tuple[float, float, float, float],
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    value = bpy.data.materials.new(
        name=name
    )
    value.diffuse_color = color
    value.use_nodes = True

    principled = value.node_tree.nodes.get(
        "Principled BSDF"
    )
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = 0.35
    principled.inputs["Metallic"].default_value = 0.15

    if emission_strength > 0:
        principled.inputs["Emission Color"].default_value = color
        principled.inputs["Emission Strength"].default_value = (
            emission_strength
        )

    return value


def add_channel_frame(
    length: float,
    width: float,
    height: float,
) -> None:
    bpy.ops.mesh.primitive_cube_add(
        location=(0, 0, 0)
    )
    channel = bpy.context.object
    channel.name = "FreeCAD_Flow_Domain"
    channel.dimensions = (
        length,
        width,
        height,
    )
    bpy.ops.object.transform_apply(
        location=False,
        rotation=False,
        scale=True,
    )

    frame_material = material(
        "ChannelFrame",
        (0.03, 0.35, 0.8, 1.0),
        emission_strength=0.25,
    )
    channel.data.materials.append(
        frame_material
    )

    wireframe = channel.modifiers.new(
        name="EngineeringWireframe",
        type="WIREFRAME",
    )
    wireframe.thickness = 0.025
    wireframe.use_replace = True


def add_flow_particles(
    length: float,
    width: float,
    height: float,
    speeds: list[float],
    frame_end: int,
) -> None:
    colors = (
        (0.05, 0.35, 1.0, 1.0),
        (0.0, 0.9, 0.85, 1.0),
        (1.0, 0.35, 0.05, 1.0),
    )

    particle_materials = [
        material(
            f"VelocityBand_{index}",
            color,
            emission_strength=2.5,
        )
        for index, color in enumerate(
            colors
        )
    ]

    lane_y = (
        -width * 0.28,
        0.0,
        width * 0.28,
    )
    lane_z = (
        -height * 0.22,
        0.0,
        height * 0.22,
    )

    particle_index = 0

    for speed_index, speed in enumerate(
        speeds
    ):
        normalized_speed = speed / max(
            speeds
        )

        for row in range(3):
            for column in range(3):
                fraction = (
                    particle_index % 9
                ) / 9.0
                start_x = (
                    -length / 2
                    + fraction * length * 0.55
                )
                end_x = min(
                    length / 2,
                    start_x
                    + length * normalized_speed,
                )

                bpy.ops.mesh.primitive_ico_sphere_add(
                    subdivisions=2,
                    radius=0.07,
                    location=(
                        start_x,
                        lane_y[column],
                        lane_z[row],
                    ),
                )
                particle = bpy.context.object
                particle.name = (
                    f"CFD_Particle_{particle_index:02d}"
                )
                particle.data.materials.append(
                    particle_materials[
                        speed_index
                    ]
                )

                particle.keyframe_insert(
                    data_path="location",
                    frame=1,
                )
                particle.location.x = end_x
                particle.keyframe_insert(
                    data_path="location",
                    frame=frame_end,
                )

                particle_index += 1


def add_text(
    body: str,
    location: tuple[float, float, float],
    size: float,
) -> bpy.types.Object:
    bpy.ops.object.text_add(
        location=location,
        rotation=(
            math.radians(68),
            0,
            0,
        ),
    )
    text_object = bpy.context.object
    text_object.data.body = body
    text_object.data.align_x = "CENTER"
    text_object.data.size = size
    text_object.data.extrude = 0.008
    text_object.data.materials.append(
        material(
            f"TextMaterial_{text_object.name}",
            (0.85, 0.95, 1.0, 1.0),
            emission_strength=0.4,
        )
    )
    return text_object


def point_camera(
    camera: bpy.types.Object,
    target: tuple[float, float, float],
) -> None:
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat(
        "-Z",
        "Y",
    ).to_euler()


def configure_scene(
    scene: bpy.types.Scene,
    frame_end: int,
) -> None:
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = frame_end

    scene.world.color = (
        0.005,
        0.008,
        0.02,
    )

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = os.path.join(
        FRAME_DIRECTORY,
        "flow_",
    )


def main() -> None:
    os.makedirs(
        RESULT_DIRECTORY,
        exist_ok=True,
    )
    os.makedirs(
        FRAME_DIRECTORY,
        exist_ok=True,
    )

    freecad = load_json(
        FREECAD_MANIFEST
    )
    openfoam = load_json(
        OPENFOAM_SUMMARY
    )

    freecad_geometry = freecad["geometry"]
    cfd_geometry = openfoam["geometry_m"]

    expected_geometry = {
        "length": freecad_geometry["length_m"],
        "width": freecad_geometry["width_m"],
        "height": freecad_geometry["height_m"],
    }

    if expected_geometry != cfd_geometry:
        raise RuntimeError(
            "FreeCAD and OpenFOAM geometry dimensions do not match."
        )

    clear_scene()
    scene = bpy.context.scene
    frame_end = 96
    configure_scene(
        scene=scene,
        frame_end=frame_end,
    )

    display_scale = 40.0
    length = cfd_geometry["length"] * display_scale
    width = cfd_geometry["width"] * display_scale
    height = cfd_geometry["height"] * display_scale

    add_channel_frame(
        length=length,
        width=width,
        height=height,
    )

    velocity = openfoam[
        "final_fields"
    ]["velocity_magnitude_m_per_s"]
    speeds = [
        velocity["minimum"],
        velocity["mean"],
        velocity["maximum"],
    ]
    add_flow_particles(
        length=length,
        width=width,
        height=height,
        speeds=speeds,
        frame_end=frame_end,
    )

    add_text(
        "FreeCAD 1.0.2  →  OpenFOAM 12  →  Blender 5.0.1",
        (0, 1.8, 2.4),
        0.34,
    )
    add_text(
        (
            "200 × 50 × 20 mm | 1,600 CFD cells | "
            f"Umean {velocity['mean']:.3f} m/s | "
            f"Umax {velocity['maximum']:.3f} m/s"
        ),
        (0, 1.4, 1.85),
        0.24,
    )

    bpy.ops.object.camera_add(
        location=(
            9.8,
            -11.5,
            7.2,
        )
    )
    camera = bpy.context.object
    camera.name = "PortfolioCamera"
    camera.data.lens = 52
    point_camera(
        camera,
        (0, 0, 0.45),
    )
    scene.camera = camera

    bpy.ops.object.light_add(
        type="AREA",
        location=(0, -1.5, 6.5),
    )
    key_light = bpy.context.object
    key_light.data.energy = 1300
    key_light.data.shape = "RECTANGLE"
    key_light.data.size = 8

    bpy.ops.object.light_add(
        type="AREA",
        location=(-5, 4, 3.5),
    )
    fill_light = bpy.context.object
    fill_light.data.energy = 850
    fill_light.data.color = (
        0.18,
        0.4,
        1.0,
    )
    fill_light.data.size = 5

    bpy.ops.wm.save_as_mainfile(
        filepath=BLEND_PATH
    )
    bpy.ops.render.render(
        animation=True
    )

    frame_files = sorted(
        os.path.join(
            FRAME_DIRECTORY,
            filename,
        )
        for filename in os.listdir(
            FRAME_DIRECTORY
        )
        if filename.lower().endswith(
            ".png"
        )
    )

    if len(frame_files) != frame_end:
        raise RuntimeError(
            "Blender did not produce the expected "
            f"{frame_end} animation frames; "
            f"found {len(frame_files)}."
        )

    shutil.copyfile(
        frame_files[
            len(frame_files) // 2
        ],
        PREVIEW_PATH,
    )

    final_manifest = {
        "workflow": "freecad_openfoam_blender",
        "status": "completed",
        "stages": [
            "freecad_geometry",
            "openfoam_simulation",
            "blender_animation",
        ],
        "versions": {
            "freecad": "1.0.2",
            "openfoam": "12",
            "blender": bpy.app.version_string,
        },
        "geometry_m": cfd_geometry,
        "mesh_cells": openfoam["mesh"]["cells"],
        "velocity_magnitude_m_per_s": velocity,
        "artifacts": {},
        "animation": {
            "format": "PNG_sequence",
            "frame_count": len(frame_files),
            "frames_per_second": scene.render.fps,
            "duration_seconds": (
                len(frame_files)
                / scene.render.fps
            ),
        },
    }

    for name, path in {
        "freecad_manifest": FREECAD_MANIFEST,
        "openfoam_summary": OPENFOAM_SUMMARY,
        "blend": BLEND_PATH,
        "preview": PREVIEW_PATH,
    }.items():
        final_manifest["artifacts"][name] = {
            "path": path,
            "size_bytes": os.path.getsize(path),
            "sha256": sha256(path),
        }

    sequence_digest = hashlib.sha256()

    for frame_path in frame_files:
        sequence_digest.update(
            bytes.fromhex(
                sha256(frame_path)
            )
        )

    final_manifest["artifacts"][
        "animation_frames"
    ] = {
        "directory": FRAME_DIRECTORY,
        "frame_count": len(frame_files),
        "size_bytes": sum(
            os.path.getsize(frame_path)
            for frame_path in frame_files
        ),
        "sequence_sha256": (
            sequence_digest.hexdigest()
        ),
        "first_frame": frame_files[0],
        "last_frame": frame_files[-1],
    }

    with open(
        FINAL_MANIFEST,
        "w",
        encoding="utf-8",
    ) as manifest_file:
        json.dump(
            final_manifest,
            manifest_file,
            indent=2,
        )

    print(
        json.dumps(
            final_manifest,
            indent=2,
        )
    )
    print("BLENDER_FLOW_ANIMATION_OK")


main()

