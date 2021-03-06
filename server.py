import tornado
from tornado import web
from tornado.web import RequestHandler
from tornado.options import define, options
from tornado.websocket import WebSocketHandler
import serial
import os
import threading
import queue
import json
import time

from sqlalchemy import *
from sqlalchemy.orm import *
from sqlalchemy.ext.declarative import declarative_base

terminals = []

def str2HexList(strObj):
    '''字符串转十六进制列表'''
    ret = []
    for i, l in enumerate(strObj):
        if i%2:
            ret[i//2] = ret[i//2]+int(l)
        else:
            r = int(l) * 16
            ret.append(r)

    print(ret)
    return ret

Base = declarative_base()

terminals = []

class Terminal:
    def __init__(self,
        name,
        department,
        level,
        uid,
        gid,
        tid,
        x=0,y=0,onlineFlag=False):
        self.name = name
        self.depatment = department
        self.level = level
        self.uid = uid
        self.gid = gid
        self.tid = tid
        self.x = x
        self.y = y

# class Terminal(Base):
#     '''记录类型'''
#     __tablename__ = 'chart_posdata'
#     name = Column(String(10))      # 姓名
#     depatment = Column(String(10))      # 科室
#     level = Column(String(10))     # 职级
#     uid = Column(String(30),primary_key=True)       # 工号
#     gatewayId = Column(String(30))     # 对应网关id
#     x = Column(Integer)
#     tid = Column(String(30))       # 标签id
#     onlineFlag = Column(Integer)
#     y = Column(Integer)

class Result:
    def __init__(self, needToWeb, id=None, msgType=None, msg=None, tid=None):
        self.needToWeb = needToWeb
        self.tid = tid
        self.message = {'id':id, 'type':msgType, 'message':msg}

class MySerial(serial.Serial):
    '''串口处理'''
    def __init__(self, port='COM11'):
        print('myserial init')
        try:
            super().__init__(port=port, baudrate=115200, timeout=1)
        except:
            print("serial open failed")
            super().close()
            super().open()
        self.sendQueue = queue.Queue(maxsize=50)
        self.recvQueue = queue.Queue(maxsize=50)
        t = threading.Thread(target=self.loop, name='serail_loop')
        t.start()
    
    def rxProtocol(self, buff):
        '''协议处理'''
        if buff[0] == 0x02 and buff[1] == 0x07:
            '''报警信息上报'''
            strObj = '%02x%02x' % (buff[4],buff[5])
            print(strObj)
            print(terminals)
            i = 0
            for terminal in terminals:
                if terminal.tid == strObj:
                    result = Result(True, terminal.uid, 0x07, 'none', tid=[buff[4],buff[5]])
                    break
                else:
                    i += 1
            if i >= len(terminals): 
                return Result(False)
        elif buff[0] == 0x02 and buff[1] == 0x08:
            print('''定位信息上传''')
            strObj = '%02x%02x' % (buff[4],buff[5])
            i = 0
            for terminal in terminals:
                if terminal.tid == strObj:
                    pos = {'x':buff[6]*16+buff[7],'y':buff[8]*16+buff[9]}
                    terminal.x = pos['x']   # 更新坐标值
                    terminal.y = pos['y']
                    result = Result(True, terminal.uid, 0x08, pos, tid=[buff[4],buff[5]])
                else:
                    i += 1
            if i >= len(terminals): 
               	return Result(False)
        elif buff[0] == 0x02 and buff[1] == 0x00:
            '''网关上线'''
            result = Result(False, str(buff[2]), 0x00)
        elif buff[0] == 0x02 and buff[1] == 0x09:
            '''消息已读上报'''
            result = Result(False, str(buff[2]), tid=[buff[4],buff[5]])
        else:
            '''网关应答'''
            result = Result(False)
        print(result.message)
        return result
    
    def checkAck(self, result):
        '''检查应答'''
        for i in range(5):
            buff = self.read(2048)
            if not buff:
                continue
            if buff[0] == 0x02 and buff[1] == result[1]:
                print("recv ack")
                return True
            else:
                continue
        return False
    
    def loop(self):
        global websocks
        while True:
            # 发送队列优先级高于接收队列
            while not self.sendQueue.empty():
                '''发送队列非空'''
                print('serial loop')
                msg = self.sendQueue.get_nowait()   # 从队列中取出一个消息
                print(msg)
                for i in range(3):
                    self.write(msg)
                    if self.checkAck(msg):          # 收到应答，跳出
                        break
            '''处理上报数据'''
            buff = self.read(2048)
            if not buff:
                continue
            print(buff)
            result = self.rxProtocol(buff)
            if result.needToWeb:
                '''需要在页面上更新，转json格式'''
                message = json.dumps(result.message)
                print(message)
                for websock in websocks:
                    websock.write_message(message.encode('utf-8'))
            if result.message['id'] == None:
                continue
            resp = [0x03, buff[1], buff[2]]
            if result.tid == None:
                resp.append(0x00)
            else:
                resp.extend(result.tid)
                resp.insert(3,len(result.tid))
            check = 0       # 校验位
            for x in resp:
                check = check ^ x
            resp.append(check)
            self.write(resp)

define("port",default=8080,type=int)
define("ip",default="127.0.0.1",type=str)

class IndexHandler(RequestHandler):
    def get(self):
        # terminals = session.query(Terminal).all()
        self.render("myindex.html",terminals=terminals)
    
    def post(self):
        # 清除记录
        global terminals
        terminals = []
        # terminals = session.query(Terminal).all()
        # print(terminals)
        # for terminal in terminals:
        #     session.delete(terminal)
        # session.commit()
        # 获取POST数据
        data = {}
        commitList = []
        content = (self.request.files['csvfile'][0]['body'][:-2])
        terminalDatas = content.decode('GB2312').split('\r\n')
        print(terminalDatas)
        for i, terminalData in enumerate(terminalDatas):
            column = terminalData.split(',')
            if i == 0:      # 第一行
                for key in column:
                    data[key] = None
            else:
                for value, key in zip(column, data.keys()):
                    data[key] = value
                 
                dataSet = Terminal(
                    data['姓名'],
                    data['科室'],
                    data['职称'],
                    data['工号'],
                    data['对应网关'],
                    data['标签id']
                )
                terminals.append(dataSet)
                
                # dataSet.name = data['姓名']
                # dataSet.depart = data['科室']
                # dataSet.level = data['职称']
                # dataSet.uid = data['工号']
                # dataSet.tid = data['标签id']
                # dataSet.gatewayId = data['对应网关']
                # dataSet.onlineFlag = True
                # dataSet.x = 0
                # dataSet.y = 0
                # commitList.append(dataSet)
                # print(commitList)
        # session.add_all(commitList)
        # session.commit()
        # terminals = session.query(Terminal).all()
        print(terminals)
        print(dir(Terminal))
        self.render("myindex.html",terminals=terminals)

        
        

websocks = set()

def WebProtocol(buff):
    jsonDict = json.loads(buff)
    print(jsonDict)
    res = []
    global terminals
    if jsonDict['type'] == 0x02:
        # 定时轮询开关
        result = [0x03,0x02,jsonDict['id'],0x01,jsonDict['message']]
        res.append(result)
    elif jsonDict['type'] == 0x01:
        # 时间同步
        result = [0x03,0x01,jsonDict['id'],19]
        tm = time.localtime()
        tm_s = '{:4}.{:0>2}.{:0>2},{:0>2}:{:0>2}:{:0>2}'.format(
            tm.tm_year, tm.tm_mon, tm.tm_mday, \
            tm.tm_hour, tm.tm_min, tm.tm_sec
        )
        rb = bytes(tm_s, encoding='utf-8')
        rl = list(rb)
        result.extend(rl)
        res.append(result)
    elif jsonDict['type'] == 0x03:
        # 个人信息更新
        for terminal in terminals:
            if terminal.uid == jsonDict['id']:
                terminal.name = jsonDict['message']['name']
                terminal.depatment = jsonDict['message']['depart']
                terminal.level = jsonDict['message']['level']
                terminal.uid = jsonDict['message']['uid']
                # 个人信息组帧
                # 姓名
                result = [0x03,0x03,0x01]
                s = '{:0>4}'.format(terminal.tid)   # 字符串转换
                l = str2HexList(s)
                result.extend(l)            # 追加至返回列表中
                r = terminal.name
                rb = bytes(r, encoding='GB2312')
                length = len(rb)
                rl = list(rb)
                result.extend(rl)
                result.insert(3, length+2)
                res.append(result)
                # 科室和职级
                result = [0x03,0x04,0x01]
                s = '{:0>4}'.format(terminal.tid)   # 字符串转换
                l = str2HexList(s)
                result.extend(l)            # 追加至返回列表中
                r = '%s %s' % (terminal.depatment, terminal.level)
                rb = bytes(r, encoding='GB2312')
                length = len(rb)
                rl = list(rb)
                result.extend(rl)
                result.insert(3, length+2)
                res.append(result)
                # 工牌号
                result = [0x03,0x05,0x01]
                s = '{:0>4}'.format(terminal.tid)   # 字符串转换
                l = str2HexList(s)
                result.extend(l)            # 追加至返回列表中
                r = '{0}'.format(terminal.uid)
                rb = bytes(r, encoding='utf-8')
                length = len(rb)
                rl = list(rb)
                result.extend(rl)
                result.insert(3, length+2)
                res.append(result)
                break
    elif jsonDict['type'] == 0x04:
        # 向下发送数据
        # terminals = session.query(Terminal).all() # 获取所有数据集
        for terminal in terminals:
            # 姓名
            result = [0x03,0x03,0x01]
            s = '{:0>4}'.format(terminal.tid)   # 字符串转换
            l = str2HexList(s)
            result.extend(l)            # 追加至返回列表中
            r = terminal.name
            rb = bytes(r, encoding='GB2312')
            length = len(rb)
            rl = list(rb)
            result.extend(rl)
            result.insert(3, length+2)
            res.append(result)
            # 科室和职级
            result = [0x03,0x04,0x01]
            s = '{:0>4}'.format(terminal.tid)   # 字符串转换
            l = str2HexList(s)
            result.extend(l)            # 追加至返回列表中
            r = '%s %s' % (terminal.depatment, terminal.level)
            rb = bytes(r, encoding='GB2312')
            length = len(rb)
            rl = list(rb)
            result.extend(rl)
            result.insert(3, length+2)
            res.append(result)
            # 工牌号
            result = [0x03,0x05,0x01]
            s = '{:0>4}'.format(terminal.tid)   # 字符串转换
            l = str2HexList(s)
            result.extend(l)            # 追加至返回列表中
            r = '{0}'.format(terminal.uid)
            rb = bytes(r, encoding='utf-8')
            length = len(rb)
            rl = list(rb)
            result.extend(rl)
            result.insert(3, length+3)
            res.append(result)
    elif jsonDict['type'] == 0x06:
        # 消息推送
        for terminal in terminals:
            if terminal.uid == jsonDict['id']:
                result = [0x03,0x06,0x01]
                s = '{:0>4}'.format(terminal.tid)   # 字符串转换
                l = str2HexList(s)
                result.extend(l)
                r = jsonDict['message']
                rb = bytes(r, encoding='GB2312')
                length = len(rb)
                rl = list(rb)
                result.extend(rl)
                result.insert(3, length+2)
                res.append(result)
                break
            elif jsonDict['id'] == 'All':
                result = [0x03,0x06,0x01]
                s = '{:0>4}'.format(terminal.tid)   # 字符串转换
                l = str2HexList(s)
                result.extend(l)
                r = jsonDict['message']
                rb = bytes(r, encoding='GB2312')
                length = len(rb)
                rl = list(rb)
                result.extend(rl)
                result.insert(3, length+2)
                res.append(result)

    for r in res:
        check = 0       # 校验位
        for x in r:
            check = check ^ x
        r.append(check)
    return res

class MyWebSocket(WebSocketHandler):
    '''web socket 处理'''
    global websocks

    def open(self):
        '''连接'''
        print("websocket open")
        websocks.add(self)
    
    def on_message(self,message):
        '''收到web端消息'''
        global ms
        result = WebProtocol(message)
        for msgdata in result:
            print(msgdata)
            ms.sendQueue.put_nowait(msgdata)
            # 等待应答
        self.write_message(message)

    def on_close(self):
        websocks.remove(self)
        print('%d' % len(websocks))

    def check_origin(self,origin):
        return True

if __name__ == "__main__":
    ms = MySerial(port='COM11')     # 初始化串口

    # 初始化数据库连接
    path = os.path.join(os.path.dirname(__file__), "db.sqlite3")
    engine = create_engine(r'sqlite:///' + path)
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    session.close()
    
    print(dir(Terminal))
    
    tornado.options.parse_command_line()
    app = tornado.web.Application(
        [
            (r'/', IndexHandler),
            (r'/web/', MyWebSocket)
        ],
        static_path = os.path.join(os.path.dirname(__file__),"static"),
        template_path = os.path.join(os.path.dirname(__file__),"templates"),
        debug = False
        )
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port,options.ip)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except:
        tornado.ioloop.IOLoop.instance().stop()
    print("end")