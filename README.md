# Airbnb MongoDB Analytics

Project for the Big Data and Data Modelling course, Masters in Data Science and Advanced Analytics, NOVA IMS.  
This repository reflects a cleaned version of the project, with improved organisation and documentation for clarity and reproducibility.

---

## Project Authors

João Paulo de Ávila – 20250436 – [20250436@novaims.unl.pt](mailto:20250436@novaims.unl.pt)  
Lucas Campos Ferreira – 20250448 – [20250448@novaims.unl.pt](mailto:20250448@novaims.unl.pt)  
Pedro Miguel Gaspar Santos – 20250399 – [20250399@novaims.unl.pt](mailto:20250399@novaims.unl.pt)  
Pedro Miguel Gonçalves Fernandes – 20250418 – [20250418@novaims.unl.pt](mailto:20250418@novaims.unl.pt)

---

## Project Overview

This project was developed as a consulting assignment for the Airbnb Business Intelligence Department, using the Inside Airbnb dataset (~5,500 listings across multiple cities).  
The objective is to redesign the raw MongoDB database from a single flat collection into a well-structured, pattern-driven data model that supports recurring analytical queries across five analytical roles: pricing, ratings, amenities, host performance, and property features.

---

## Project Goals

1. **Database redesign** – Split the source collection into normalised collections (`listings`, `reviews`, `hosts`, `listing_text`) using embedding, referencing, and pattern-driven choices.
2. **Data cleaning** – Detect and handle duplicates, missing values, type inconsistencies, malformed fields, and invalid ranges.
3. **Pattern application** – Apply Subset, Computed, Extended Reference, Attribute, Outlier, and Schema Versioning patterns where analytically justified.
4. **Index strategy** – Design and register indexes tied to real query patterns, supporting efficient filtering by city, host type, ratings, amenities, and availability.
5. **Host performance analysis - My role in the Project (Role D)** – Analyse host type vs pricing, host features vs satisfaction with query optimisation, and popularity metrics for professional hosts.

---

## Usage

- Run the notebook to reproduce the full workflow from database preparation to final analysis.
- All helper functions, indexes, and computed fields are defined inline and self-contained within the notebook.
- Use `explain_compare()` to reproduce before/after query performance comparisons for each optimised pipeline.

---

## Outcome

A fully restructured MongoDB database with:

- **`listings`** – main analytical entity with computed fields (`host_type`, `popularity_score`, `price_ppn_2g`, `price_ppn_3g`, `size_category`, `reviews_subset`, `is_mega_host`)
- **`reviews`** – full review history preserved via referencing
- **`hosts`** – host-level aggregates with precomputed binary features (`is_fast_responder`, `is_perfect_responder`, `is_flexible_cancellation`, `avg_rating`)
- **`listing_text`** – text-heavy fields separated to reduce document scan weight

---

## Data

The raw database archive is provided as `BDMM_HW_Database_NEW`. Import it into MongoDB before running the notebook.

```bash
docker run --name mongodbHW -d \
  -e MONGO_INITDB_ROOT_USERNAME=AzureDiamond \
  -e MONGO_INITDB_ROOT_PASSWORD=hunter2 \
  -p 27017:27017 mongo
```

Then import `BDMM_HW_Database_NEW` via Studio 3T or Compass using the BSON mongodump archive format.

---

## Notebook

- **BDMM_18.ipynb** – full pipeline: database setup, cleaning, schema redesign, pattern application, index registration, and analytical tasks A–E
