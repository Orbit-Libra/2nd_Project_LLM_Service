#!/usr/bin/env python3
"""
pipeline_runtime_tracer.py

Drop-in lightweight tracer for your pipeline steps. Use it to log stage transitions,
inputs/outputs, and durations, then convert logs to Mermaid sequence/flow diagrams.

USAGE:
  from pipeline_runtime_tracer import Stage

  with Stage("DataHandling.run", outputs=["data/intermediate/2024_clean.csv"]):
      # do work...
      pass

  with Stage("DBHandling.upload_to_oracle",
             consumes=["data/intermediate/2024_clean.csv"],
             outputs=["Oracle:TABLE=LIBRA.SCORES"]):
      # upload...
      pass
"""
import json, os, time, uuid
from contextlib import contextmanager
from datetime import datetime

TRACE_FILE = os.environ.get("PIPELINE_TRACE_FILE", "pipeline_trace.log")

@contextmanager
def Stage(name: str, consumes=None, outputs=None, meta=None):
    t0 = time.time()
    rec = {
        "id": str(uuid.uuid4()),
        "name": name,
        "ts_start": datetime.utcnow().isoformat()+"Z",
        "consumes": consumes or [],
        "outputs": outputs or [],
        "meta": meta or {},
    }
    try:
        yield
        rec["status"] = "ok"
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = repr(e)
        raise
    finally:
        rec["ts_end"] = datetime.utcnow().isoformat()+"Z"
        rec["duration_s"] = round(time.time()-t0, 3)
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False)+"\n")
