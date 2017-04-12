#!/usr/bin/env python
# coding: utf-8


import sys
reload(sys) # Python2.5 初始化后会删除 sys.setdefaultencoding 这个方法，我们需要重新载入
sys.setdefaultencoding('utf-8')

from wxbot import *
import ConfigParser
import datetime
import json
import redis


class TulingWXBot(WXBot):
    def __init__(self):
        WXBot.__init__(self)

        self.tuling_key = ""
        self.robot_switch = True
        self.booking = False
        self.redis = redis.Redis(host='127.0.0.1', port=6379,db=0)

        try:
            cf = ConfigParser.ConfigParser()
            cf.read('conf.ini')
            self.tuling_key = cf.get('main', 'key')
        except Exception:
            pass
        print 'tuling_key:', self.tuling_key

    def tuling_auto_reply(self, uid, msg):
        if self.tuling_key:
            url = "http://www.tuling123.com/openapi/api"
            user_id = uid.replace('@', '')[:30]
            body = {'key': self.tuling_key, 'info': msg.encode('utf8'), 'userid': user_id}
            r = requests.post(url, data=body)
            respond = json.loads(r.text)
            result = ''
            if respond['code'] == 100000:
                result = respond['text'].replace('<br>', '  ')
                result = result.replace(u'\xa0', u' ')
            elif respond['code'] == 200000:
                result = respond['url']
            elif respond['code'] == 302000:
                for k in respond['list']:
                    result = result + u"【" + k['source'] + u"】 " +\
                        k['article'] + "\t" + k['detailurl'] + "\n"
            else:
                result = respond['text'].replace('<br>', '  ')
                result = result.replace(u'\xa0', u' ')

            print '    ROBOT:', result
            return result
        else:
            return u"知道啦"

    def auto_switch(self, msg):
        msg_data = msg['content']['data']
        stop_cmd = [u'退下', u'走开', u'关闭', u'关掉', u'休息', u'88']
        start_cmd = [u'出来', u'启动', u'工作', u'hi']
        if self.robot_switch:
            for i in stop_cmd:
                if i == msg_data:
                    self.robot_switch = False
                    self.send_msg_by_uid(u'[Robot]' + u'机器人已关闭！', msg['to_user_id'])
        else:
            for i in start_cmd:
                if i == msg_data:
                    self.robot_switch = True
                    self.send_msg_by_uid(u'[Robot]' + u'机器人已开启！', msg['to_user_id'])

    def handle_msg_all(self, msg):
        #{'content': {'data': u'test', 'desc': u'test', 'type': 0, 'user': {'id': u'@7b70c26fbdcaf3c6649effcefb17a0b141ab4ed0442b2b850215134b8033be14', 'name': u'Jimmy'}, 'detail': [{'type': 'str', 'value': u'test'}]}, 
        #'msg_id': u'8876228969116942459', 'msg_type_id': 3, 'to_user_id': u'5', 'user': {'id': u'@@cf0658939de72ca756a24a102950008446167779a7bec41cb100e087121d689c', 'name': 'unknown'}}
        if not self.robot_switch and msg['msg_type_id'] != 1:
            return
        if msg['msg_type_id'] == 1 and msg['content']['type'] == 0:  # reply to self
            self.auto_switch(msg)
        elif msg['msg_type_id'] == 4 and msg['content']['type'] == 0:  # text message from contact
            self.send_msg_by_uid(self.tuling_auto_reply(msg['user']['id'], msg['content']['data']), msg['user']['id'])
        elif msg['msg_type_id'] == 3 and msg['content']['type'] == 0:  # group text message
            if 'detail' in msg['content']:
                my_names = self.get_group_member_name(msg['user']['id'], self.my_account['UserName'])
                if my_names is None:
                    my_names = {}
                if 'NickName' in self.my_account and self.my_account['NickName']:
                    my_names['nickname2'] = self.my_account['NickName']
                if 'RemarkName' in self.my_account and self.my_account['RemarkName']:
                    my_names['remark_name2'] = self.my_account['RemarkName']

                is_at_me = False
                #print '    Me:', my_names
                #print '    Detail:', msg['content']['detail']
                for detail in msg['content']['detail']:
                    if detail['type'] == 'at':
                        for k in my_names:
                            if my_names[k] and my_names[k] == detail['value']:
                                is_at_me = True
                                break
                    elif detail['type'] == 'str':
                        for k in my_names:
                            if detail['value'].find(my_names[k]) > -1:
                                is_at_me = True
                                break

                #print '    @Me:', is_at_me

                if is_at_me:
                    src_name = self.get_group_member_name(msg['user']['id'], msg['content']['user']['id'])
                    #print '    src:', src_name
                    if src_name is None:
                        sourceName = ''
                    elif 'display_name' in src_name:
                        sourceName = src_name['display_name']
                    elif 'nickname' in src_name:
                        sourceName = src_name['nickname']
                    else:
                        sourceName = ''

                    desc = msg['content']['desc']
                    for k in my_names:
                        desc = desc.replace("@" + my_names[k], '', 10)
                    bookingCount = desc.strip("+").strip("＋").strip("加").strip()
                    if self.booking and bookingCount.isdigit():
                        if sourceName == '':
                            self.send_msg_by_uid("to 那个谁: 我不认识你", msg['user']['id'])
                        else:
                            if int(bookingCount) > 10:
                                self.send_msg_by_uid("@" + sourceName + ": 你吃得了那么多吗, 我这干活呢, 一边玩儿去 Ծ‸Ծ", msg['user']['id'])
                            elif int(bookingCount) < 0:
                                self.send_msg_by_uid("@" + sourceName + ": 小屁孩, 我这干活呢, 一边玩儿去 Ծ‸Ծ", msg['user']['id'])
                            elif int(bookingCount) == 0:
                                self.redis.hdel("supper", sourceName)
                                self.send_msg_by_uid("@" + sourceName + ": 你取消了订晚餐", msg['user']['id'])
                            else:
                                self.redis.hset("supper", sourceName, int(bookingCount))
                                self.send_msg_by_uid("@" + sourceName + ": 你订了" + str(int(bookingCount)) + "份晚餐", msg['user']['id'])
                    elif desc == "统计结果":
                        result = self.redis.hgetall("supper")
                        total = 0;
                        details = u',其中\n';
                        for n in result.keys():
                            if result[n] <> '0':
                                total += int(result[n])
                                details += n + "预定了"+result[n]+'份\n'
                        if total > 0:
                            self.send_msg_by_uid(u"总共"+str(total)+"份"+details, msg['user']['id'])
                        else:
                            self.send_msg_by_uid(u"还没有人订餐呢", msg['user']['id'])
                    elif desc == "通知大家来取餐票":
                        if sourceName == 'Jimmy' or sourceName == u"赵嫦娥":
                            supperResult = self.redis.hgetall("supper")
                            names = u'';
                            for n in supperResult.keys():
                                if supperResult[n] <> '0':
                                    names += '@'+n+" "
                            self.send_msg_by_uid(names + " 请找 @赵嫦娥 领取晚餐票", msg['user']['id'])
                        else:
                            self.send_msg_by_uid("to 那个谁: 我不听你的", msg['user']['id'])
                    elif desc == "开始统计晚餐":
                        if sourceName == 'Jimmy' or sourceName == u"赵嫦娥":
                            self.redis.delete("supper")
                            self.booking = True
                            self.send_msg_by_uid("@所有人 开始统计加班晚餐啦,要吃的报名啦", msg['user']['id'])
                        else:
                            self.send_msg_by_uid("to 那个谁: 我不听你的", msg['user']['id'])
                    elif desc == "停止统计晚餐":
                        if sourceName == 'Jimmy' or sourceName == u"赵嫦娥":
                            self.booking = False
                            self.send_msg_by_uid("@所有人 不再接受订餐了", msg['user']['id'])
                        else:
                            self.send_msg_by_uid("to 那个谁: 我不听你的", msg['user']['id'])
                    else:
                        if sourceName == '':
                            reply = 'to 那个谁: '
                        else:
                            reply = '@' + sourceName + ' '

                        now = datetime.datetime.now()
                        self.redis.rpush("talks", now.strftime('%Y-%m-%d %H:%M:%S') + " " + sourceName + ":" + msg['content']['desc'])

                        if msg['content']['type'] == 0:  # text message
                            reply += self.tuling_auto_reply(msg['content']['user']['id'], desc)
                        else:
                            reply += u"对不起，只认字，其他杂七杂八的我都不认识，,,Ծ‸Ծ,,"
                        self.send_msg_by_uid(reply, msg['user']['id'])


def main():
    bot = TulingWXBot()
    bot.DEBUG = True
    bot.conf['qr'] = 'png'

    bot.run()


if __name__ == '__main__':
    main()

