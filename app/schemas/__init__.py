# 导入常用模型，方便其他模块引用
from .admin import Admin, AdminCreate, AdminUpdate
from .class_ import Class, ClassCreate, ClassUpdate
from .student import Student, StudentCreate, StudentUpdate
from .task import Task, TaskCreate, TaskUpdate, TaskDetail
from .task import StudentTask, StudentTaskCreate, StudentTaskDetail
from .environment import EnvironmentTemplate, EnvironmentTemplateCreate, EnvironmentTemplateUpdate, EnvironmentTemplateDetail
from .ecs import ECSInstance, ECSInstanceCreate, ECSInstanceUpdate
from .guacamole import GuacamoleConnection, GuacamoleConnectionCreate, GuacamoleCredentials
from .jupyter import JupyterContainer, JupyterContainerCreate, JupyterAccessInfo