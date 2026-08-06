# Preliminary Filter Evaluation Data

Store local evaluation datasets here while tuning Phase 5.7.

Do not commit CRM exports, real user vacancy datasets, resume URLs, cookies,
storage state, phone numbers, SMS codes or personal notes.

JSON datasets are ignored by default, except `example.synthetic.json`.

Run:

``` powershell
cd worker
.\api\.venv\Scripts\python.exe .\tools\evaluate_preliminary_filter.py .\evaluation_data\example.synthetic.json
```
