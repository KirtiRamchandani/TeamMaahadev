# Team Maahadev

<img src="https://think360studio-media.s3.ap-south-1.amazonaws.com/download/india-flag-2021-wallpaper-1.png" alt="India Flag" width="200" height="100">

## Members

| Full Name of Participant              | Role                                | Responsibilities                                       |
|--------------------------------------|-------------------------------------|--------------------------------------------------------|
| **Kirtikumar Anandrao Ramchandani**  | Software Engineer & Security Researcher | AI Developer, Automation Engineer & Data Analyst       |
| **Priyank Lalitbhai Basrani**        | Electronics & Communication Engineer | Hardware Hacker, Systems Integrator                    |

---

## Table of Contents
- [Module A: Planning](#module-a-planning)
- [Module B: Model Design](#module-b-model-design)
- [Module C: Fuzz Testing](#module-c-fuzz-testing)
- [Module D: Drone & Neural Network Integration](#module-d-drone--neural-network-integration)
- [Module E: Final Model Presentation](#module-e-final-model-presentation)
- [PTL3D: Automated Power Transmission Line Reconstruction](#ptl3d-automated-power-transmission-line-reconstruction)

---

## [Module A: Planning](./Module_A/README.md)
- [Project structure planning](./Module_A/README.md)
- [Team role assignments](./Module_A/README.md)
- [Timeline and task allocation](./Module_A/README.md) 

---

## Module B: Model Design
- [Design and architecture diagrams](./Module_B/Architecture.md)  
- [Dataset approach and preparation](./Module_B/dataset_approach.md)  
- [Mathematical foundations](./Module_B/Math_equations.md)  
- [GeoPackage layers overview](./Module_B/geo_package_layers_overview.png)  
- Neural Network 1 and 2 training reports  
- Tower and wire alignment analysis  
  - [Tower axis alignment](./Module_B/tower_axis_alignment.png)  
  - [Wire sag profile](./Module_B/wire_sag_profile.png)

---

## Module C: Fuzz Testing
- [Fuzzing methodology and test plan](./Module_C/fuzz_testing.md)  
- [Testing and coverage metrics](./Module_C/testing.md)  
- Mutation logs:  
  - [mutationlog.json](./Module_C/mutationlog.json)  
  - [mutationlog2.json](./Module_C/mutationlog2.json)  
- Visual outputs:  
  - [Fuzzing console view](./Module_C/fuzzing_console_view.png)  
  - [Fuzzing heatmap](./Module_C/fuzzing_heatmap.png)  
  - [Fuzzing mIoU graph](./Module_C/fuzzing_graph_miou.png)  
  - [Fuzzing demonstration video](./Module_C/fuzzing_demo.mp4)

---

## Module D: Drone & Neural Network Integration
- Neural Network integration with UAV sensor data  
- Drone control firmware integration  
- Web dashboard and visualization panel  
- Powerline dataset preprocessing and coordinate alignment

**Refer `src/`**
---

## Module E: Final Model Presentation
- [Final presentation slides (PPTX)]
- [Real-time video: Traffic Light Detection via Drone Neural Network]

---

# PTL3D: Automated Power Transmission Line Reconstruction

An AI-powered geospatial pipeline that reconstructs **3D digital twins** of power transmission lines from Airborne Laser Scanning (ALS) and Aerial Photogrammetry (AP) data.

---

## Goal

To create a fully automated 3D reconstruction of:
- **Tower axes** (LineStringZ)  
- **Wire attachment (insulator) points** (PointZ)  
- **Wire catenaries** (LineStringZ)

All results are exported as a **GeoPackage** (`.gpkg`) aligned with the terrain model for GIS visualization and analysis.

---

## Dataset

Dataset: [Download Here](https://disk.yandex.ru/d/abJf69-FB_qesQ)  
Password: `20251105`

---
