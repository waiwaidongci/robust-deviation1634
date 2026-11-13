import json,time,traceback
from pathlib import Path
from .config.database import Base,engine,SessionLocal
from .config.settings import ARTIFACTS_DIR
from .models import DeviationRun
from .models.migrations import ensure_schema
from .constants.status import RunStatus
from .services.run_service import queue
from .services.analysis_service import analyze_deviation
from .services.audit_service import log
Base.metadata.create_all(engine);ensure_schema();Path(ARTIFACTS_DIR).mkdir(exist_ok=True)
while True:
    Path(ARTIFACTS_DIR,"heartbeat").write_text(str(time.time()))
    job=queue.blpop("deviation:jobs",timeout=2)
    if not job:continue
    with SessionLocal() as db:
        run=db.get(DeviationRun,int(job[1]))
        if not run or run.status!=RunStatus.QUEUED:continue
        run.status=RunStatus.RUNNING;db.commit()
        try:
            run.result=analyze_deviation(run.input_snapshot,run.alpha,run.seed,run.error_control);run.status=RunStatus.COMPLETED
            Path(ARTIFACTS_DIR,f"run-{run.id}.json").write_text(json.dumps(run.result,ensure_ascii=False));log(db,"worker","deviation.completed",run.id)
        except Exception as e:run.status=RunStatus.FAILED;run.error=str(e);traceback.print_exc()
        db.commit()
