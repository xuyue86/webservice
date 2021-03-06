import json
import requests
from flask import Blueprint
import config
import log
import pymysql
import re
import datetime 
from service.openstack.keystone import commonfun
from service.openstack.keystone import make_response
from flask import request
monitormod = Blueprint('monitormod', __name__)

def getNicsInfo(output):
        obj={}
        infos = output.split(',')
        for info in infos:
            res = info.split('=',1)
            if res[0]=='name' :
                obj['name'] = res[1]
            elif res[0]=='status' :
                obj['status'] = res[1]
            elif res[0]=='in' :
                obj['inbound_rate'] = res[1]
            elif res[0]=='out' :
                obj['outbound_rate'] = res[1]
            elif res[0]=='mac' :
                obj['mac_address'] = res[1]
        return obj

def getDisksInfo(output):
    obj={}
    infos = output.split(',')
    for info in infos:
        res = info.split('=',1)
        if(res[0]=='name'):
            obj['name'] = res[1]
        elif(res[0]=='cap'):
            obj['capacity'] = res[1]
        elif(res[0]=='usage'):
            obj['usage'] = res[1][:-1]
        elif(res[0]=='readiops'):
            obj['read_iops'] = res[1]
        elif(res[0]=='writeiops'):
            obj['write_iops'] = res[1]
        elif(res[0]=='rthroughput'):
            obj['read_throughput'] = res[1]
        elif(res[0]=='wthroughput'):
            obj['write_throughput'] = res[1]
    return obj
def getDBConn():
    print config.notification_db_config['db_host']+':'+str(config.notification_db_config['db_port'])
    conn = pymysql.connect(host=config.notification_db_config['db_host'],
                           port=config.notification_db_config['db_port'],
                           user=config.notification_db_config['db_user'],
                           passwd=config.notification_db_config['db_pass'],
                           db=config.notification_db_config['db_schema'],
                           charset='utf8',
                           cursorclass=pymysql.cursors.DictCursor)
    return conn



@monitormod.route('/v1/server/<server_id>/monitor',methods=['GET'])
def get_server_monitor(server_id):
    conn = getDBConn() 
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_server_monitor', (server_id,))
        resultSet = cursor.fetchall()
        server_monitor={}
        if len(resultSet) > 0 :
            server_monitor['server_id']=server_id
            server_monitor['cpu_usage']=''
            server_monitor['mem_usage']=''
            server_monitor['status']='active'
            server_monitor['running_time']=''
            server_monitor['health_status']=''
            server_monitor['nics']=[]
            server_monitor['disks']=[]
            for result in resultSet:
                name = result.get('name','').lower()
                output = result.get('output','').lower()
                if name == 'uptime':
                    server_monitor['running_time']=output.split('=',1)[1]
                elif name == 'cpu usage':
                    server_monitor['cpu_usage']=output.split('=',1)[1][:-1]
                elif name == 'memory usage':
                    server_monitor['mem_usage']=output.split('=',1)[1][:-1]
                elif name == 'health_status':
                    server_monitor['health_status']=output
                elif name.startswith('eth'):
                    server_monitor['nics'].append(getNicsInfo(output))
                elif name.startswith('disk'):
                    server_monitor['disks'].append(getDisksInfo(output))
        cursor.close()
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'server_monitor':server_monitor}), 200)

@monitormod.route('/v1/host/<host_id>/monitor',methods=['GET'])
def get_host_monitor(host_id):
    conn = getDBConn()
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_host_monitor', (host_id,))
        resultSet = cursor.fetchall()
        host_monitor={}
        if len(resultSet) > 0 :
            host_monitor['host_id']=host_id
            host_monitor['cpu_usage']=''
            host_monitor['mem_usage']=''
            host_monitor['power_status']='active'
            host_monitor['running_time']=''
            host_monitor['health_status']=''
            host_monitor['nics']=[]
            host_monitor['disks']=[]
            for result in resultSet:
                name = result.get('name','').lower()
                output = result.get('output','').lower()
                if output=='':
                    continue
                if name=='uptime':
                    host_monitor['running_time']=output.split('=',1)[1]
                elif name=='cpu usage':
                    host_monitor['cpu_usage']=output.split('=',1)[1][:-1]
                elif name=='memory usage':
                    host_monitor['mem_usage']=output.split('=',1)[1][:-1]
                elif name=='health_status':
                    host_monitor['health_status']=output.lower()
                elif name.startswith('eth'):
                    host_monitor['nics'].append(getNicsInfo(output))
                elif name.startswith('disk'):
                    host_monitor['disks'].append(getDisksInfo(output))
        cursor.close()
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'host_monitor':host_monitor}), 200)

@monitormod.route('/v1/network_device/<network_device_id>/monitor',methods=['GET'])
def get_network_device_monitor(network_device_id):
    def getMB(unit):
        if unit=='g':
            return 1024.0
        elif unit =='k':
            return 1/1024.0
        else:
            return 1
    def getBanwidth(output):
        pattern = re.compile('avg\. in = (\d+\.?\d*) ([k|m|g]?)b/s, avg\. out = (\d+\.?\d*) ([k|m|g]?)b/s')
        res = pattern.search(output).groups()
        if(len(res)==4):
            return {'in_rate':res[0],'in_rate_unit':res[1],'out_rate':res[2],'out_rate_unit':res[3]} 
        else:
            return None
    def getPowerStatus(output):
        if output.find('power=ok') < 0:
            return 'down'
        else:   
            return 'active'
    conn = getDBConn()
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_network_device_monitor', (network_device_id,))
        resultSet = cursor.fetchall()
        network_monitor={}
        if len(resultSet) > 0 :
            network_monitor['network_device_id']=network_device_id
            network_monitor['cpu_usage']=''
            network_monitor['ram_usage']=''
            network_monitor['power_status']=''
            network_monitor['inbound_rate']=''
            network_monitor['outbound_rate']=''
            network_monitor['health_status']=''
            inbound_rate = 0.0
            outbound_rate = 0.0
            cpu_usage = 0.0
            cpu_count=0.0
            mem_usage = 0.0
            mem_count=0.0
            is_multi_cpu = False;
            is_multi_mem = False;
            for result in resultSet:
                name = result.get('name','').lower()
                output = result.get('output','').lower()
                if output=='':
                    continue
                if name == 'loadavg':
                    if output.find('chassis') >= 0:
                        is_multi_cpu = True
                        cpu_list = output.split(',')
                        for cpu in cpu_list:
                            cpu_usage += int(cpu.split('=',1)[1][:-1])
                            cpu_count += 1
                    else:    
                        network_monitor['cpu_usage']=output.replace(' ','').split('=',1)[1][:-1]
                elif name == 'memutil':
                    if output.find('chassis') >= 0:
                        is_multi_mem = True
                        chassis_list = output.split(' chassis')
                        for chassis in chassis_list:
                            mem_list = chassis.split('=',1)[1].split(',')
                            for mem in mem_list:
                                if mem == '':
                                    continue
                                mem_usage += int(mem[:-1])
                                mem_count += 1
                    else:
                        network_monitor['ram_usage']=output.split('=',1)[1][:-1]
                elif name.endswith('bandwidth usage'):
                    inout_rate = getBanwidth(output)
                    if inout_rate != None:
                        if inout_rate['in_rate_unit']!='':
                            inbound_rate += float(inout_rate['in_rate'])*getMB(inout_rate['in_rate_unit'])
                        if inout_rate['out_rate_unit']!='':
                            outbound_rate += float(inout_rate['out_rate'])*getMB(inout_rate['out_rate_unit'])
                elif name == 'health_status':
                    network_monitor['health_status']=output
                elif name == 'environment':
                    network_monitor['power_status']=getPowerStatus(output)
            if is_multi_cpu:
                network_monitor['cpu_usage'] = str(int(round(cpu_usage/cpu_count)))
            if is_multi_mem:
                network_monitor['ram_usage'] = str(int(round(mem_usage/mem_count)))
            network_monitor['inbound_rate'] = str(round(inbound_rate,2))
            network_monitor['outbound_rate'] = str(round(outbound_rate,2))
        cursor.close()
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'network_monitor':network_monitor}), 200)

@monitormod.route('/v1/warn_strategies/<strategy_id>',methods=['GET'])
def get_warn_strategies(strategy_id):
    conn = getDBConn()
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_warn_strategy_detail', (strategy_id,))
        warn_strategy={}
        result = cursor.fetchone()
        if result==None:
            return make_response('Resource not Found',404)
        warn_strategy['id']=result.get('id','');
        warn_strategy['tenant_id']=result.get('tenant_id','');
        warn_strategy['name']=result.get('name','');
        warn_strategy['type']=result.get('type');
        warn_strategy['level']=result.get('warn_level');
        warn_strategy['relationship']=result.get('relationship','');
        warn_strategy['rules']=[];
        cursor.nextset()
        resultSet = cursor.fetchall()
        for result in resultSet:
            rule={}
            rule['field']=result.get('field','')
            rule['comparison']=result.get('comparison','')
            rule['threshold']=result.get('threshold','')
            warn_strategy['rules'].append(rule)

        warn_strategy['servers']=[];
        cursor.nextset()
        resultSet = cursor.fetchall()
        for result in resultSet:
            warn_strategy['servers'].append(result.get('server_id',''))
        cursor.close()
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'warn_strategy':warn_strategy}), 200)

@monitormod.route('/v1/warn_strategies',methods=['GET'])
def get_warn_strategies_list():
    conn = getDBConn()
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_warn_strategies')
        warn_strategys=[]
        warn_id_dict={}
        resultSet = cursor.fetchall()
        for result in resultSet:
            warn_strategy={}
            warn_strategy['id']=result.get('id','');
            warn_strategy['tenant_id']=result.get('tenant_id','');
            warn_strategy['name']=result.get('name','');
            warn_strategy['type']=result.get('type','');
            warn_strategy['level']=result.get('warn_level','');
            warn_strategy['relationship']=result.get('relationship','');
            warn_strategy['rules']=[];
            warn_strategy['servers']=[];
            warn_id_dict[result['id']]=warn_strategy
            warn_strategys.append(warn_strategy)

        cursor.nextset()
        resultSet = cursor.fetchall()
        for result in resultSet:
            rule={}
            rule['field']=result.get('field','')
            rule['comparison']=result.get('comparison','')
            rule['threshold']=result.get('threshold','')
            warn_id_dict[result['strategy_id']]['rules'].append(rule)

        cursor.nextset()
        resultSet = cursor.fetchall()
        for result in resultSet:
            warn_id_dict[result['strategy_id']]['servers'].append(result['server_id'])
        cursor.close()
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'warn_strategys':warn_strategys}), 200)

@monitormod.route('/v1/device/warnings/<warn_id>',methods=['GET'])
def get_device_warnings(warn_id):
    conn = getDBConn()
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_device_warnings_detail',(warn_id,))
        result = cursor.fetchone()
        warning={}
        if result==None:
            return make_response('Resource not Found',404)
        warning['id']=result['id']
        warning['strategy_id']=result.get('strategy_id','')
        warning['name']=result.get('name','')
        warning['type']=result.get('type','')
        warning['description']=result.get('description','')
        warning['level']=result.get('level','')
        warning['object_id']=result.get('object_id','')
        warning['object_type']=result.get('object_type','')
        warning['created']=str(result.get('created',''))
        warning['status']=result.get('status','')
        cursor.close()
    except Exception as exc:
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'warnings':warning}), 200)

@monitormod.route('/v1/device/warnings',methods=['GET'])
def get_device_warnings_list():
    requestParam = {}
    requestParam['order_by'] = request.args.get('order_by', 'created_time')
    requestParam['desc'] = request.args.get('desc', 'false')
    requestParam['start_time'] = request.args.get('start_time', None)
    requestParam['end_time'] = request.args.get('end_time', None)
    conn = getDBConn()
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_device_warnings',(requestParam['start_time'],requestParam['end_time'] ))
        resultSet = cursor.fetchall()
        warnings=[]
        for result in resultSet:
            warning={}
            warning['id']=result.get('id','')
            warning['strategy_id']=result.get('strategy_id','')
            warning['name']=result.get('name','')
            warning['type']=result.get('type','')
            warning['description']=result.get('description','')
            warning['level']=result.get('level','')
            warning['object_id']=result.get('object_id','')
            warning['object_type']=result.get('object_type','')
            warning['created']=str(result.get('created',''))
            warning['status']=result.get('status','')
            warnings.append(warning)
        cursor.close()
        if len(warnings)>0 :
            warnings = sorted(warnings, key=lambda k: k['created'],reverse= (requestParam['desc']=='true'))
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'warnings':warnings}), 200)

@monitormod.route('/v1/server/warnings',methods=['GET'])
def get_server_warnings_list():
    requestParam = {}
    requestParam['order_by'] = request.args.get('order_by', 'created_time')
    requestParam['desc'] = request.args.get('desc', 'false')
    requestParam['start_time'] = request.args.get('start_time', None)
    requestParam['end_time'] = request.args.get('end_time', None)
    requestParam['user_id'] = request.args.get('user_id', None)
    requestParam['tenant_id'] = request.args.get('tenant_id', None)
    if requestParam['tenant_id']== None:
        return make_response('tenant_id is null', 400)
    conn = getDBConn()
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_server_warnings',(requestParam['user_id'],requestParam['tenant_id'],requestParam['start_time'],requestParam['end_time'] ))
        resultSet = cursor.fetchall()
        warnings=[]
        for result in resultSet:
            warning={}
            warning['id']=result.get('id','')
            warning['tenant_id']=result.get('tenant_id','')
            warning['strategy_id']=result.get('strategy_id','')
            warning['name']=result.get('name','')
            warning['type']=result.get('type','')
            warning['description']=result.get('description','')
            warning['level']=result.get('level','')
            warning['server_id']=result.get('server_id','')
            warning['created']=str(result.get('created',''))
            warning['status']=result.get('status','')
            warnings.append(warning)
        cursor.close()
        if len(warnings)>0 :
            warnings = sorted(warnings, key=lambda k: k['created'],reverse= (requestParam['desc']=='true'))
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'warnings':warnings}), 200)

@monitormod.route('/v1/server/warnings/<warn_id>',methods=['GET'])
def get_server_warnings(warn_id):
    conn = getDBConn()
    warning={}
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_server_warnings_detail',(warn_id,))
        result = cursor.fetchone()
        print result
        if result==None:
            return make_response('Resource not Found',404)
        warning['id']=result['id']
        warning['tenant_id']=result.get('tenant_id','')
        warning['strategy_id']=result.get('strategy_id','')
        warning['name']=result.get('name','')
        warning['type']=result.get('type','')
        warning['description']=result.get('description','')
        warning['level']=result.get('level','')
        warning['server_id']=result.get('server_id','')
        warning['created']=str(result.get('created',''))
        warning['status']=result.get('status','')
        cursor.close()
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'warnings':warning}), 200)

@monitormod.route('/v1/storage_device/<storage_id>/monitor',methods=['GET'])
def get_storage_monitor(storage_id):
    def getIOValue(output):
        total = 0
        nodes = result.get('output','').lower().split(',')
        for node in nodes:
            total+=int(node.split('=',1)[1])
        return total
    def getTPValue(output):
        total = 0
        nodes = result.get('output','').lower().replace(' ','').split(',')
        for node in nodes:
            total+=int(node.split('=',1)[1][:-2])
        return total
    def getPowerStatus(output):
        if output.find('power=ok') <0:
            return 'down'
        else:   
            return 'active'
    conn = getDBConn()
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_get_storage_device_monitor', (storage_id,))
        resultSet = cursor.fetchall()
        storage_monitor={}
        if len(resultSet) > 0 :
            storage_monitor['storage_id']=storage_id
            storage_monitor['read_iops']=''
            storage_monitor['write_iops']=''
            storage_monitor['read_throughput']=''
            storage_monitor['write_throughput']=''
            storage_monitor['health_status']=''
            storage_monitor['power_status']=''
            storage_monitor['free_space']=''
            read_iops=0
            write_iops=0
            read_throughput=0
            write_throughput=0
            for result in resultSet:
                name = result.get('name','').lower()
                output = result.get('output','').lower()
                if output=='':
                    continue
                if name=='readiops':
                    read_iops += getIOValue(output)
                elif name=='writeiops':
                    write_iops += getIOValue(output)
                elif name=='readthroughput':
                    read_throughput += getTPValue(output)
                elif name=='writethroughput':
                    write_throughput += getTPValue(output)
                elif name=='freespace':
                    storage_monitor['free_space'] = output.split('=',1)[1].split(' ',1)[0]
                elif name=='health_status':
                    storage_monitor['health_status'] = output
                elif name=='environment':
                    storage_monitor['power_status'] = getPowerStatus(output)
            storage_monitor['read_iops']=str(read_iops)
            storage_monitor['write_iops']=str(write_iops)
            storage_monitor['read_throughput']=str(read_throughput)
            storage_monitor['write_throughput']=str(write_throughput)
        cursor.close()
    except Exception as exc:
        log.error(exc)
        return make_response(json.dumps(exc.message), 500)
    finally:
        conn.close()
    return make_response(json.dumps({'storage_monitor':storage_monitor}), 200)
