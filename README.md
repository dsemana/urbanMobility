# NYC Taxi Intelligence Dashboard
### Full-Stack Urban Mobility Analytics · January 2019 TLC Dataset

---
# AI Usage Declaration

**Project:** NYC Taxi Mobility Dashboard

---

## Where AI was used

### ✅ Understanding the assignment brief
Used AI to clarify requirements, decompose tasks, and discuss what the deliverables should cover — such as what a normalised schema means, what feature engineering involves, and what constitutes a meaningful visualisation.

### ✅ Conceptual explanations
Asked AI to explain concepts encountered during the project — for example, star schema design principles, what makes an outlier in trip data, and how Flask routing works — to deepen understanding before applying them independently.

### ✅ Interpreting data findings
Discussed patterns observed in the dataset with AI to sanity-check interpretations — for instance, whether a 45% speed drop during rush hours is realistic, or what might explain Manhattan's 90.7% trip share.

### ✅ Interpreting data findings
We used AI to find the python concepts that can be used to execute this application

---

## Where AI was not used

### ❌ Code generation
All code — the data pipeline (`pipeline.py`), the Flask API (`app.py`), and the frontend (`index.html`, `app.js`, `styles.css`) — was written entirely by the student without AI assistance.

### ❌ Database design
The relational schema — including the star schema structure, table definitions, column types, foreign key relationships, indexes, and the seven pre-aggregated summary tables — was designed independently by the student.

### ❌ System design and architecture
The three-layer architecture (data pipeline → SQLite → Flask API → browser), the ERD, and the decision to serve the frontend statically from Flask were all decisions made by the student.

### ❌ Data cleaning decisions and feature engineering
The eight exclusion rules, their thresholds, and the three derived features (`trip_duration_min`, `speed_mph`, `tip_pct`) were identified, justified, and implemented by the student.

---

## What this app does

Processes **7.49 million NYC yellow taxi trips** from January 2019 into a clean relational database, serves the data through a REST API, and visualises it in an interactive dashboard.

```
