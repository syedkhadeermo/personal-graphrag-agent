import json
import os

import FreeCAD
import Part


OUTPUT_DIRECTORY = r"C:\AI_Worker\results\cad_flow_channel"
FCSTD_PATH = os.path.join(
    OUTPUT_DIRECTORY,
    "flow_channel.FCStd",
)
STEP_PATH = os.path.join(
    OUTPUT_DIRECTORY,
    "flow_channel.step",
)
MANIFEST_PATH = os.path.join(
    OUTPUT_DIRECTORY,
    "flow_channel_manifest.json",
)

LENGTH_MM = 200.0
WIDTH_MM = 50.0
HEIGHT_MM = 20.0


def main() -> None:
    os.makedirs(
        OUTPUT_DIRECTORY,
        exist_ok=True,
    )

    document = FreeCAD.newDocument(
        "PortfolioFlowChannel"
    )

    flow_domain = document.addObject(
        "Part::Feature",
        "FlowDomain",
    )
    flow_domain.Label = "OpenFOAM Flow Domain"
    flow_domain.Shape = Part.makeBox(
        LENGTH_MM,
        WIDTH_MM,
        HEIGHT_MM,
    )

    flow_domain.addProperty(
        "App::PropertyLength",
        "ChannelLength",
        "Geometry",
    )
    flow_domain.addProperty(
        "App::PropertyLength",
        "ChannelWidth",
        "Geometry",
    )
    flow_domain.addProperty(
        "App::PropertyLength",
        "ChannelHeight",
        "Geometry",
    )
    flow_domain.addProperty(
        "App::PropertyString",
        "DownstreamTool",
        "Workflow",
    )

    flow_domain.ChannelLength = LENGTH_MM
    flow_domain.ChannelWidth = WIDTH_MM
    flow_domain.ChannelHeight = HEIGHT_MM
    flow_domain.DownstreamTool = "OpenFOAM 12"

    document.recompute()
    document.saveAs(FCSTD_PATH)

    Part.export(
        [flow_domain],
        STEP_PATH,
    )

    bounding_box = flow_domain.Shape.BoundBox

    manifest = {
        "workflow": "freecad_openfoam_blender",
        "stage": "freecad_geometry",
        "status": "completed",
        "units": "millimetres",
        "geometry": {
            "type": "rectangular_flow_domain",
            "length_mm": LENGTH_MM,
            "width_mm": WIDTH_MM,
            "height_mm": HEIGHT_MM,
            "length_m": LENGTH_MM / 1000.0,
            "width_m": WIDTH_MM / 1000.0,
            "height_m": HEIGHT_MM / 1000.0,
            "volume_mm3": flow_domain.Shape.Volume,
            "bounding_box_mm": {
                "x_length": bounding_box.XLength,
                "y_length": bounding_box.YLength,
                "z_length": bounding_box.ZLength,
            },
        },
        "artifacts": {
            "fcstd": FCSTD_PATH,
            "step": STEP_PATH,
            "manifest": MANIFEST_PATH,
        },
        "downstream": {
            "tool": "OpenFOAM",
            "version": "12",
            "mesh_cells": [40, 10, 4],
            "inlet_velocity_m_per_s": 1.0,
        },
    }

    with open(
        MANIFEST_PATH,
        "w",
        encoding="utf-8",
    ) as manifest_file:
        json.dump(
            manifest,
            manifest_file,
            indent=2,
        )

    print(
        json.dumps(
            manifest,
            indent=2,
        )
    )
    print("FREECAD_FLOW_CHANNEL_OK")

    FreeCAD.closeDocument(
        document.Name
    )


main()
