from sqlalchemy import *
from sqlalchemy.orm import *
from sqlalchemy.ext.declarative import declarative_base
import os

Base = declarative_base()

class Terminal(Base):
    __tablename__ = 'chart_posdata'
    name = Column(String(10))      # 姓名
    depatment = Column(String(10))      # 科室
    level = Column(String(10))     # 职级
    tid = Column(String(30))       # 标签id
    uid = Column(String(30),primary_key=True)       # 工号
    gatewayId = Column(String(30))     # 对应网关id
    onlineFlag = Column(Integer)
    x = Column(Integer)
    y = Column(Integer)

path = os.path.join(os.path.dirname(__file__), "db.sqlite3")
print(path)

engine = create_engine(r'sqlite:///' + path)
DBSession = sessionmaker(bind=engine)
session = DBSession()
for terminal in session.query(Terminal).all():
    print(terminal.name)

def func():
    print(i)

if __name__ == '__main__':
    i = 1
    func()