from sqlalchemy import Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
SINGLE_WINDOW='single_window'
FAMILY_WISE='family_wise_holm'
class DeviationRun(Base):
    __tablename__="deviation_runs"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]
    study_id:Mapped[int]=mapped_column(ForeignKey("archive_studies.id"))
    alpha:Mapped[float]=mapped_column(Double)
    seed:Mapped[int]
    # 创建时冻结的误报控制：single_window=旧单窗边际规则；family_wise_holm=整批Holm族系校正
    error_control:Mapped[str]=mapped_column(default=SINGLE_WINDOW)
    input_snapshot:Mapped[dict]=mapped_column(JSON)
    status:Mapped[str]=mapped_column(default="queued")
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    error:Mapped[str]=mapped_column(Text,default="")
    owner:Mapped[str]
    created_at:Mapped[str]=mapped_column(default=now)
