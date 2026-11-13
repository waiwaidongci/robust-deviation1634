from pydantic import BaseModel,Field,ConfigDict
from ..models.deviation_run import SINGLE_WINDOW,FAMILY_WISE
class RunInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str=Field(min_length=2,max_length=120)
    study_id:int
    alpha:float=Field(default=.05,ge=.01,le=.2,allow_inf_nan=False)
    seed:int=Field(default=2026,ge=0,le=2147483647,strict=True)
    # 创建研究时冻结：单窗边际（旧规则）或整批Holm族系校正；提交后不可改
    error_control:str=Field(default=FAMILY_WISE,pattern=f"^({SINGLE_WINDOW}|{FAMILY_WISE})$")
