# Drone Agri Segmentation — Full Pipeline

 ## 1. Project Setup & Data Prep

```mermaid
flowchart LR
    A[Clone Repo / Setup Env] --> B[Load PNG Masks]
    B --> C[Define Class List]
    C --> D{Masks Valid and Consistent}
    D -- Yes --> E[Split Train/Val]
    D -- No --> F[Fix Palette or Size Issues]
    F --> C
```

---

 ## 2. Training Workflow

```mermaid
flowchart LR
    A[Start Training] --> B[DataLoader: resize, pad, crop, augment]
    B --> C[UNet++ Forward Pass with ResNet Backbone]
    C --> D[Deep Supervision Heads]
    D --> E[Compute Loss: CE + Dice + Focal]
    E --> F[Backprop with AdamW]
    F --> G[Cosine LR + Warmup]
    G --> H[EMA Update of Weights]
    H --> I{End of Epoch}
    I -- Validate --> J[Evaluate on Val Set with EMA Model]
    J --> K[Save Top-K Checkpoints by mIoU]
    I -- More Epochs --> B
    I -- Finished --> L[Training Summary + Best Checkpoint]
```

---

 ## 3. AI Segmentation Training Workflow
   
```mermaid
flowchart TD
    A["Prepare Patches from Cloud"] --> B["Class Balance and Stratified Sampling"]
    B --> C["Augmentation - rotate jitter scale"]
    C --> D["Model Choice - PointNetpp or RandLANet"]
    D --> E["Forward Pass"]
    E --> F["Loss - weighted CE plus focal"]
    F --> G["Optimizer - AdamW"]
    G --> H["Scheduler - cosine with warmup"]
    H --> I["EMA Shadow Weights"]
    I --> J{"End of Epoch"}
    J -->|Validate| K["Compute mIoU and per class IoU"]
    K --> L{"New Best Metrics"}
    L -->|Yes| M["Save Checkpoint and Log"]
    L -->|No| N["Continue Training"]
    J -->|More Epochs| C
    J -->|Finished| O["Export Best Model and Training Report"]
```

 ## 4. Inference and Reconstruction Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as Command Line
    participant SEG as Segmentation Model
    participant FE as Feature Extraction
    participant RE as 3D Reconstruction
    participant EXP as GeoPackage Export
    participant QGIS as QGIS

    User->>CLI: run infer on segment file
    CLI->>SEG: load model and run segmentation on preprocessed cloud
    SEG-->>CLI: labeled point cloud
    CLI->>FE: detect towers and insulator points
    FE-->>CLI: tower centroids and attachment points
    CLI->>RE: fit catenaries and build tower axes
    RE-->>CLI: 3D lines for wires and towers
    CLI->>EXP: assemble attributes and write gpkg layers
    EXP-->>CLI: gpkg path and logs
    User->>QGIS: open gpkg and validate with orthomosaic and dtm
```

 ## 5.  Feature Extraction Detail

```mermaid
flowchart LR
    A["Segmented Cloud"] --> B["Tower Cluster Isolation - DBSCAN"]
    B --> C["Centroid and Peak Detection"]
    C --> D["Build tower_axis as LineStringZ"]
    D --> E["Cross Arm Region Search"]
    E --> F["Attachment Point Candidate Scoring"]
    F --> G{"Geometric Consistency Pass"}
    G -->|Pass| H["Accept Insulator Points"]
    G -->|Fail| I["Refine Candidates and Retry"]
    H --> J["Output tower_axis and insulator"]
```

 ## 6.  Wire Fitting Logic

```mermaid
flowchart TD
    A["Insulator Pairs by Span"] --> B{"Enough points between towers"}
    B -->|Yes| C["Catenary Fit with least squares"]
    B -->|No| D["Parabolic Approximation"]
    C --> E{"Max sag within bounds"}
    D --> E
    E -->|Yes| F["Create wire LineStringZ"]
    E -->|No| G["Robust fit with RANSAC then create LineStringZ"]
```

 ## 7. Export and Validation

```mermaid
flowchart LR
    A["3D Geometries and Attributes"] --> B["GeoPandas DataFrames"]
    B --> C["Write GeoPackage with GDAL and Fiona"]
    C --> D["Layer: tower_axis"]
    C --> E["Layer: insulator"]
    C --> F["Layer: wire"]
    D --> G["Run schema checks"]
    E --> G
    F --> G
    G --> H["Visual QA in QGIS"]
```

 ## 8. Quality Gates and Error Handling State Machine

```mermaid
stateDiagram-v2
    [*] --> Ingest
    Ingest --> Preprocess: files valid
    Ingest --> Reject: missing or corrupt files

    Preprocess --> Segmentation: stats ok and density ok
    Preprocess --> Repair: inconsistent CRS or color map
    Repair --> Preprocess

    Segmentation --> Features: mIoU above threshold
    Segmentation --> Retrain: mIoU below threshold
    Retrain --> Segmentation

    Features --> Reconstruct: tower and insulator counts sane
    Features --> TuneParams: failed geometry checks
    TuneParams --> Features

    Reconstruct --> Export: reconstruction ok
    Reconstruct --> TuneParams

    Export --> Validate
    Validate --> [*]: approved
    Validate --> Investigate: spatial misalignment
    Investigate --> Preprocess
```

 ## 9. GeoPackage Schema as ER Diagram

```mermaid
erDiagram
    TOWER_AXIS ||--o{ INSULATOR : has
    INSULATOR ||--o{ WIRE : anchors
    TOWER_AXIS {
        int id
        int id_tower
        LineStringZ geom
        float height
        float tilt_deg
    }
    INSULATOR {
        int id
        int id_tower
        int id_wire
        PointZ geom
        float elevation_m
    }
    WIRE {
        int id
        int id_insulator_start
        int id_insulator_end
        LineStringZ geom
        float sag_m
        float length_m
    }
```

 ## 10. Orchestration and Parallelization DAG

```mermaid
flowchart TD
    subgraph Stage 1
    A1["Tile Cloud"] --> A2["Distribute Tiles"]
    end

    subgraph Stage 2
    P1["Preprocess Tile 1"] 
    P2["Preprocess Tile 2"]
    P3["Preprocess Tile N"]
    end

    subgraph Stage 3
    S1["Segment Tile 1"]
    S2["Segment Tile 2"]
    SN["Segment Tile N"]
    end

    subgraph Stage 4
    F1["Features Tile 1"]
    F2["Features Tile 2"]
    FN["Features Tile N"]
    end

    subgraph Stage 5
    M["Merge Features"]
    R["Global Reconstruction"]
    end

    A2 --> P1
    A2 --> P2
    A2 --> P3

    P1 --> S1
    P2 --> S2
    P3 --> SN

    S1 --> F1
    S2 --> F2
    SN --> FN

    F1 --> M
    F2 --> M
    FN --> M

    M --> R
```

 ## 11. CI and Reproducibility Pipeline

```mermaid
flowchart LR
    A["Commit or Tag"] --> B["Unit Tests and Lint"]
    B --> C["Synthetic Cloud Smoke Tests"]
    C --> D{"Pass"}
    D -->|Yes| E["Build Docker Images"]
    D -->|No| F["Fail and Report"]
    E --> G["Integration Test on small segment"]
    G --> H{"Performance and accuracy OK"}
    H -->|Yes| I["Publish Release Artifact"]
    H -->|No| F
```

 ## 12. Data Lineage and Provenance

```mermaid
flowchart TD
    RAW["Raw Sensors and Metadata"] --> PRE["Preprocessed Cloud"]
    PRE --> SEG["Labeled Cloud"]
    SEG --> FEAT["Features Tower and Insulator"]
    FEAT --> RECON["3D Wires and Towers"]
    RECON --> GPKG["GeoPackage"]
    RAW -. audit logs .-> GPKG
    PRE -. hashes .-> GPKG
    SEG -. metrics .-> GPKG
    GPKG --> CATALOG["Dataset Catalog with checksums"]
```

 ## 13. Stakeholder Journey Diagram

```mermaid
journey
    title Workflow experience
    section Data engineer
      Ingest ALS and AP data: 4
      Fix CRS and metadata: 3
      Approve preprocessing: 5
    section ML engineer
      Train segmentation model: 4
      Validate metrics: 5
      Register checkpoint: 4
    section GIS analyst
      Inspect GeoPackage in QGIS: 5
      Run spatial QA and acceptance: 4
```

 ## 14. November 2025 Project Gantt

```mermaid
gantt
    title Module 2 and 3 Schedule - November 2025
    dateFormat  DD-MM-YYYY
    axisFormat  %d-%m

    section Design
    Architecture and data flow     :done,    des1, 10-11-2025, 2d
    Preprocess module prototype    :active,  des2, 12-11-2025, 2d

    section Modeling
    Model setup and parameters     :         mod1, 14-11-2025, 3d
    Photogrammetry integration     :         mod2, 17-11-2025, 3d

    section Reconstruction
    Geometry extraction tests      :         rec1, 20-11-2025, 4d
    Export pipeline completion     :         rec2, 24-11-2025, 2d

    section Validation
    End to end validation          :         val1, 26-11-2025, 3d
    Reporting and diagrams         :         rep1, 29-11-2025, 2d
```

 ## 15. Innovative Hybrid Segmentation Diagram

```mermaid
flowchart TD
    A["Preprocessed Cloud"] --> B["Multi scale patching"]
    B --> C1["PointNetpp logits"]
    B --> C2["RandLANet logits"]
    C1 --> D["Logit fusion with uncertainty weighting"]
    C2 --> D
    D --> E{"Confidence above threshold"}
    E -->|Yes| F["Accept class"]
    E -->|No| G["Fallback to geometric heuristics"]
    G --> H["Local plane and curvature tests"]
    H --> F
    F --> I["Final class map for features"]
```

 ## 16. Robustness and Recovery Loop
    
```mermaid
flowchart LR
    A["Pipeline start"] --> B{"CRS consistent"}
    B -->|No| C["Reproject and recheck"]
    C --> B
    B -->|Yes| D{"Point density sufficient"}
    D -->|No| E["Adaptive voxel size and retry"]
    E --> D
    D -->|Yes| F{"Segmentation mIoU above threshold"}
    F -->|No| G["Auto hyperparameter sweep and retrain"]
    G --> F
    F -->|Yes| H{"Geometry checks pass"}
    H -->|No| I["Tighten thresholds and refit"]
    I --> H
    H -->|Yes| J["Export GeoPackage"]
```

 ## 17. Minimal Examples for Quick Testing

```mermaid
flowchart TD
    X["Hello Data"] --> Y["Preprocess"]
    Y --> Z["Done"]
```
```mermaid
sequenceDiagram
    participant U as User
    participant P as Pipeline
    U->>P: run quick test
    P-->>U: success
```
