# -*- coding: utf-8 -*-
import requests
import jsonpath
import json
import logging
from logger import Mylogger

"""
CF api处理类
"""
class CFServer(object):

    def __init__(self, username, token):
        self.logger = Mylogger.getCommonLogger("cfserver.log", logging.INFO, 1)
        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.8',
            'Cache-Control': 'max-age=0',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 Safari/537.36',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'X-Auth-Email': username,
            'X-Auth-Key': token,
        }
        self.LIST_ZONES = 'https://api.cloudflare.com/client/v4/zones'
        self.LIST_DNS_RECONDS = 'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records'
        self.LIST_ORIGIN_RULES = 'https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets/phases/http_request_origin/entrypoint'
        self.session = requests.session()
    """
    获取域名列表
    zoneId：域名id
    """
    def listZones(self):
        rep = self.session.get(self.LIST_ZONES, headers=self.headers)
        if rep and rep.status_code == 200:
            data = json.loads(rep.content)
            zoneIds = jsonpath.jsonpath(data, "$.result[*].id")
            zoneNames = jsonpath.jsonpath(data, "$.result[*].name")
            return zoneIds,zoneNames
    """
    获取DNS记录列表
    zoneId：域名id
    """
    def getDNSByZoneId(self, zoneId):
        if zoneId:
            url = self.LIST_DNS_RECONDS.format(zone_id=zoneId)
            rep = self.session.get(url, headers=self.headers)
            if rep and rep.status_code == 200:
                data = json.loads(rep.content)
                dnsRecords = jsonpath.jsonpath(data, "$.result[*]")

                return dnsRecords
        return None
    def createDNSByZoneId(self,zoneId,ownDomain,servDomain,proxied):
        dnsRecordId = None
        if zoneId:
            url = self.LIST_DNS_RECONDS.format(zone_id=zoneId)
            dnsRecord = {
                "content": servDomain,
                "name": ownDomain,
                "proxied": proxied,
                "type": "CNAME"
            }
            dd = json.dumps(dnsRecord)
            rep = self.session.post(url, data=dd,headers=self.headers)
            data = json.loads(rep.content)
            result={}
            result['success'] = data['success']
            result['errors'] = data['errors']
            result['messages'] = data['messages']
            self.logger.info(f"{ownDomain} ::{result}")
            if rep and rep.status_code == 200:
                dnsRecordId = jsonpath.jsonpath(data, "$.result.id")

        return dnsRecordId

    """
    获取规则列表
    zoneId：域名id
    """
    def listOriginRules(self, zoneId):
        if zoneId:
            url = self.LIST_ORIGIN_RULES.format(zone_id=zoneId)
            rep = self.session.get(url, headers=self.headers)
            if rep and rep.status_code == 200:
                data = json.loads(rep.content)
                rules = jsonpath.jsonpath(data, "$.result[*][*]")
                return rules
        return None


    """
    更新Origin Rules
    zoneId:域名id
    
    domain:域名
    redirectPorts:待更新端口
    des:描述规则
    ruleId：规则id
    """
    def updateRuleV2(self, zoneId, updateDomains):
        if updateDomains and len(updateDomains)>0:
            rules = []
            for domain in updateDomains:
                ports = updateDomains[domain]
                if ports and len(ports)>0:
                    for p in ports:
                        result = {}
                        des = domain.split(".")[0]
                        if zoneId:
                            url = self.LIST_ORIGIN_RULES.format(zone_id=zoneId)

                            rule = {
                                "action": "route",
                                "action_parameters": {
                                    "origin": {
                                        "port": int(p)
                                    }
                                },
                                "enabled": True,
                                "description": des,
                                "expression": "(http.host eq \""+domain+"\")"
                            }
                            rules.append(rule)
            data = {"description": "domain", "rules": rules}
            dd = json.dumps(data)
            rep = self.session.put(url, data=dd, headers=self.headers)
            #self.logger.info(rep.content)
            if rep:
                data = json.loads(rep.content)
                result['success'] = data['success']
                result['errors'] = data['errors']
                result['messages'] = data['messages']
            return result

    """
    更新Origin Rules
    zoneId:域名id
    
    domain:域名
    redirectPorts:待更新端口
    des:描述规则
    ruleId：规则id
    """
    def updateRule(self, zoneId, updateDomains):
            if updateDomains and len(updateDomains)>0:
                rules = []
                for domain in updateDomains:
                    p = updateDomains[domain]
                    result = {}
                    des = domain.split(".")[0]
                    if zoneId:
                        url = self.LIST_ORIGIN_RULES.format(zone_id=zoneId)

                        rule = {
                            "action": "route",
                            "action_parameters": {
                                "origin": {
                                    "port": p
                                }
                            },
                            "enabled": True,
                            "description": des,
                            "expression": "(http.host eq \""+domain+"\")"
                        }
                        rules.append(rule)
                data = {"description": "domain", "rules": rules}
                dd = json.dumps(data)
                rep = self.session.put(url, data=dd, headers=self.headers)
                #self.logger.info(rep.content)
                if rep:
                    data = json.loads(rep.content)
                    result['success'] = data['success']
                    result['errors'] = data['errors']
                    result['messages'] = data['messages']
                return result
    """
    更新Origin Rules 主方法
    domain:域名
    ports:待更新端口
    """
    def runMain(self, ownDomain,servDomain, ports):


        updateDomains = {}
        zones,zoneNames = self.listZones()
        domain_zoneNames = dict(zip(zoneNames,zones))
        normalZoneId = 0
        #判断是否存在域名
        if ownDomain:
            for zoneName in domain_zoneNames:
                if zoneName and zoneName == ownDomain:
                    normalZoneId = domain_zoneNames[zoneName]
                    break
        if normalZoneId:

            isNormal = 0
            ownDomain = "cdn."+ownDomain
            dnsRecords = self.getDNSByZoneId(normalZoneId)
            if dnsRecords and len(dnsRecords) > 0:
                # 查找当前域名是否开启dns
                for record in dnsRecords:
                    recordName = record['name']
                    domain = recordName
                    if ownDomain in recordName:
                        isNormal = 1
                        updateDomains[recordName] = ports
                        if record['proxied']:
                            self.logger.info(domain + "::已经开启dns代理")
                        else:
                            self.logger.info(domain + "::未开启dns代理，请务必先配置")
                        break
                if not isNormal:
                    updateDomains[ownDomain] = ports
                    self.logger.info(recordName + "::未配置域名dns记录，自动帮配置")
                    self.createDNSByZoneId(normalZoneId,ownDomain,servDomain,True)

                    #else:
                    #self.logger.info(recordName + "::未配置域名dns记录，请务必先配置")


            if updateDomains and len(updateDomains)>0:
                rules = self.listOriginRules(normalZoneId)
                oldPorts = []
                for domain in updateDomains:
                    ports = updateDomains[domain]
                    key = domain
                    for port in ports:
                        key += "_"+str(port)
                    if rules and len(rules) > 0:

                        for rule in rules:
                            # 检查端口是否配置
                            expression = rule['expression']
                            rid = rule['id']
                            # 该域名已经配置规则，更新
                            if expression and domain in expression:
                                port = rule['action_parameters']['origin']['port']
                                oldPorts.append(port)
                    oldkey = domain
                    for port in oldPorts:
                        oldkey += "_"+str(port)
                if key == oldkey:
                    self.logger.info(f"{domain}:提供的新端口与旧端口一致,不操作")
                else:
                    # 创建规则
                    res = self.updateRuleV2(normalZoneId, updateDomains)
                    self.logger.info(f"{domain}:创建规则结果为:{res}")
        else:
            self.logger.info(f"{ownDomain}:未找到相关域名")
    """
   更新Origin Rules 主方法
   domain:域名
   ports:待更新端口
   """
    def runNewMain(self, domains, ports):
        domain_ports = dict(zip(domains,ports))
        updateDomains = {}
        zones = self.listZones()
        isNormal = 0
        normalZoneId = None
        if zones and len(zones) > 0:
            for zoneId in zones:
                dnsRecords = self.getDNSByZoneId(zoneId)
                if dnsRecords and len(dnsRecords) > 0:
                    # 查找当前域名是否开启dns
                    for record in dnsRecords:
                        recordName = record['name']
                        domain = recordName
                        if recordName in domain_ports:
                            updateDomains[recordName] = domain_ports[recordName]
                            if record['proxied']:
                                self.logger.info(domain + "::已经开启dns代理")
                                isNormal = 1

                            else:
                                isNormal = 1
                                self.logger.info(domain + "::未开启dns代理，请务必先配置")
                            break
                    if isNormal:

                        break
                        #else:
                        #self.logger.info(recordName + "::未配置域名dns记录，请务必先配置")
        des = domain.split(".")[0]

        if isNormal:
            if updateDomains and len(updateDomains)>0:
                rules = self.listOriginRules(normalZoneId)
                newPorts = []
                oldPorts = []
                for domain in updateDomains:
                    p = updateDomains[domain]
                    key = domain+"_"+str(p)
                    newPorts.append(key)
                    if rules and len(rules) > 0:

                        for rule in rules:
                            # 检查端口是否配置
                            expression = rule['expression']
                            rid = rule['id']
                            # 该域名已经配置规则，更新
                            if expression and domain in expression:
                                port = rule['action_parameters']['origin']['port']
                                oldKey = domain+"_"+str(port)
                                oldPorts.append(oldKey)
                pp = set(newPorts)-set(oldPorts)
                if not pp:
                    self.logger.info(f"{domain}:提供的新端口与旧端口一致,不操作")
                else:
                    # 创建规则
                    res = self.updateRule(normalZoneId, updateDomains)
                    self.logger.info(f"{domain}:创建规则结果为:{res}")
    @staticmethod
    def run(ownDomain,servDomain,ports,username,token):
        cf = CFServer(username, token)
        cf.runMain(ownDomain,servDomain,ports)
        #cf.runNewMain(ownDomain,ports)


if __name__ == '__main__':
    print("=============")

