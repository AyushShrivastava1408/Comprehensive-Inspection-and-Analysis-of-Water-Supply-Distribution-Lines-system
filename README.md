# 💧 Comprehensive Inspection and Analysis of Water Supply Distribution Lines

### An AI-Driven Video Analytics and GIS Spatial Mapping Framework

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![YOLOv8](https://img.shields.io/badge/AI-YOLOv8-purple)
![OpenCV](https://img.shields.io/badge/Computer%20Vision-OpenCV-green)
![Flask](https://img.shields.io/badge/Backend-Flask-black)
![GIS](https://img.shields.io/badge/Mapping-Leaflet.js-brightgreen)
![Project](https://img.shields.io/badge/Project-Major%20Project-orange)

## 📌 Overview

The **Comprehensive Inspection and Analysis of Water Supply Distribution Lines** is an AI-driven software framework designed to automate the inspection and analysis of water distribution pipelines.

Traditional pipeline inspection systems generate large amounts of CCTV footage that require manual examination. This process is time-consuming, expensive, and prone to human error.

Our proposed system integrates Computer Vision, Deep Learning, and Geographic Information Systems (GIS) to automatically identify visible pipeline defects, estimate their geographical locations, and provide actionable maintenance information through an interactive web-based dashboard.

The system is designed to work with existing commercial pipeline inspection crawlers without requiring modifications to their physical hardware.

## 🎯 Objectives

- Automate pipeline inspection using AI-based video analytics.
- Improve inspection video quality using OpenCV.
- Detect and classify structural pipeline defects using YOLOv8.
- Estimate defect locations using crawler distance logs and GIS data.
- Store inspection information in a centralized database.
- Visualize pipeline routes and detected defects on an interactive map.
- Support maintenance planning through automated work-order generation.

## 🚨 Problem Statement

Traditional water pipeline inspection faces several challenges:

- **Manual Inspection:** Reviewing lengthy CCTV footage requires significant time and human effort.
- **Poor Video Quality:** Low illumination, motion blur, water reflections, and noise affect defect identification.
- **Location Inaccuracy:** Crawler distance readings provide relative positions rather than absolute geographical coordinates.
- **Delayed Maintenance:** Lack of automated severity assessment makes repair prioritization difficult.
- **Operational Costs:** Manual inspection and inefficient maintenance increase operational expenses.

Our framework addresses these challenges by connecting AI-based visual inspection with spatial mapping and maintenance workflows.

## ✨ Key Features

1. **Video Processing:** Extracts frames from pipeline inspection videos using OpenCV.
2. **Image Enhancement:** Applies CLAHE, Gaussian denoising, and optical-flow-based stabilization.
3. **AI-Based Defect Detection:** Uses YOLOv8 to identify visible structural abnormalities.
4. **GPS Localization:** Maps detected defects to estimated geographical coordinates using crawler odometry.
5. **REST API:** Provides communication between the AI processing modules, database, and dashboard.
6. **GIS Visualization:** Displays pipeline routes and defect locations using Leaflet.js and OpenStreetMap.
7. **Severity Assessment:** Supports categorization and prioritization of detected defects.
8. **Maintenance Work Orders:** Supports generation of pre-filled maintenance information for critical findings.

## 🔍 Defect Detection Categories

The proposed YOLOv8 model focuses on four primary defect groups:

| Defect Category | Description |
|---|---|
| Cracks | Longitudinal and circumferential pipeline cracks |
| Joint Displacement | Misalignment or displacement between pipe joints |
| Corrosion / Spalling | Surface deterioration and material degradation |
| Blockages / Debris | Internal obstructions and accumulated debris |

## 🏗️ System Architecture

The system follows a five-phase processing architecture.

### Phase 1: Data Acquisition and Preprocessing
- Input: CCTV pipeline inspection video and crawler distance logs.
- Frame extraction using OpenCV.
- Contrast enhancement using CLAHE.
- Noise reduction using Gaussian filtering.
- Motion estimation and stabilization using Farneback Optical Flow.

### Phase 2: AI-Based Defect Detection
- Uses Ultralytics YOLOv8 with PyTorch.
- Processes enhanced video frames.
- Identifies pipeline defects.
- Generates bounding boxes, class labels, and confidence scores.

### Phase 3: Spatio-Temporal GPS Localization
- Correlates video timestamps with crawler travel-distance logs.
- Calculates relative defect positions along the pipeline.
- Maps positions onto known GIS pipeline geometry.
- Estimates corresponding Latitude and Longitude coordinates.

### Phase 4: Backend and Database Integration
- Flask REST API for communication.
- SQLAlchemy for database operations.
- MySQL / PostgreSQL with PostGIS for relational and spatial data storage.
- Stores defect information, timestamps, confidence scores, and geographical coordinates.

### Phase 5: GIS Dashboard and Maintenance
- Interactive mapping using Leaflet.js.
- OpenStreetMap integration.
- Visualization of pipeline routes and defect markers.
- Display of defect details, severity, coordinates, and inspection evidence.
- Generation of maintenance work-order information.

## 🛠️ Technology Stack

| Component | Technologies |
|---|---|
| Programming Language | Python 3.10+ |
| Computer Vision | OpenCV, NumPy, SciPy |
| Deep Learning | YOLOv8, PyTorch |
| Image Processing | CLAHE, Gaussian Filtering, Optical Flow |
| Backend | Flask REST API |
| ORM | SQLAlchemy |
| Database | MySQL / PostgreSQL |
| Spatial Database | PostGIS |
| Frontend | HTML5, CSS3, JavaScript |
| GIS Mapping | Leaflet.js, OpenStreetMap |
| Development Tools | VS Code, Jupyter Notebook |

## 🔄 End-to-End Workflow

1. Upload CCTV inspection video and crawler distance logs.
2. Extract individual frames from the inspection video.
3. Enhance and stabilize frames using OpenCV.
4. Run the YOLOv8 model on processed frames.
5. Identify defects and generate bounding boxes and confidence scores.
6. Match detection timestamps with crawler distance measurements.
7. Calculate defect locations using GIS pipeline geometry.
8. Store inspection results in the database.
9. Display pipeline routes and defect locations on the GIS dashboard.
10. Generate maintenance work orders for critical defects.

## 📂 Project Scope

- Target pipeline diameter: 100–200 mm.
- Input: Pre-recorded or streamed CCTV inspection footage.
- Input data: Crawler travel-distance / odometry logs.
- Approach: Software-centric and hardware-agnostic.
- Application: Municipal water supply distribution networks.

**Note:** This project focuses on analyzing visible internal pipeline conditions through inspection footage. It does not involve manufacturing inspection robots or modifying existing crawler hardware.

## 📊 Dataset Preparation

The project uses annotated pipeline inspection images for object detection model development.

Dataset preparation involves:

- Collecting pipeline inspection images.
- Extracting frames from CCTV footage.
- Annotating defects with YOLO-compatible bounding boxes.
- Organizing images and labels.
- Performing dataset quality checks.
- Dividing the dataset into training, validation, and testing sets.

Proposed dataset split:

| Dataset | Percentage |
|---|---:|
| Training | 70% |
| Validation | 20% |
| Testing | 10% |

## 📈 Current Development Status

| Module | Status |
|---|---|
| Literature Review | Completed |
| System Design | Completed |
| Project Manuscript | Completed |
| Dataset Collection and Annotation | In Progress |
| OpenCV Preprocessing | In Progress |
| YOLOv8 Model Training | Pending |
| GPS Localization | Pending |
| Flask API Integration | Pending |
| Database Integration | Pending |
| GIS Dashboard | Pending |

*Development status reflects the Review-I project documentation and should be updated as implementation progresses.*

## 🔮 Future Enhancements

- Improve YOLOv8 detection accuracy through dataset expansion and hyperparameter tuning.
- Integrate object tracking to reduce duplicate detections.
- Improve GPS localization accuracy under crawler odometry drift.
- Complete cloud-based API and PostGIS integration.
- Enhance automated defect severity assessment.
- Implement maintenance tracking and reporting.
- Evaluate the complete system using representative real-world inspection footage.

## 👨‍💻 Project Team

**Group 9 – AI & DS-A**

| Name | Role |
|---|---|
| Ayush Shrivastava | Project Team Member |
| Prashant Pathak | Project Team Member |
| Samar Shekhawat | Project Team Member |
| Yatharth Pareek | Project Team Member |

**Project Guide:** Prof. Sachin Chirgaiya

**Department:** Computer Science and Engineering (AI-ML)

**Institution:** Shri Vaishnav Vidyapeeth Vishwavidyalaya, Indore, Madhya Pradesh, India.

## 🎓 Academic Project

Developed as a Major Project for the Bachelor of Technology (B.Tech) program.

**Academic Session:** July–December 2026

## 📄 License

This project is developed for academic and research purposes. Licensing and reuse permissions can be defined by the project team.

---

⭐ **Our Goal:** To transform traditional pipeline inspection into an intelligent, automated, and geographically actionable maintenance system using Artificial Intelligence and GIS technology.
