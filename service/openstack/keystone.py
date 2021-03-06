import json
import requests
from flask import Blueprint
from keystoneclient.auth.identity.generic.password\
    import Password as auth_plugin
from keystoneclient import session as osc_session
from keystoneclient.v3 import client
from functools import wraps

import config
import request as httprequest
import flask
from flask import request as frequest
from werkzeug.exceptions import BadRequest


keystonemod = Blueprint('keystonemod', __name__)


def _get_user_info(user_id):
    params_no_version = {
        'username': config.admin_user,
        'project_name': config.admin_project,
        'auth_url': config.os_auth_url,
        'user_domain_id': 'default',
        'tenant_name': config.admin_project,
        'password': config.admin_passwd,
        'project_domain_id': 'default'}

    request_session = requests.session()

    auth = auth_plugin.load_from_options(**params_no_version)
    session = osc_session.Session(
        auth=auth,
        session=request_session,
        verify=True)
    ks = client.Client(session=session)
    user = ks.users.get(user_id)
    return user.name, user.default_project_id


def login(username, project_id, password, region):
    params_no_version = {
        'username': username, 'project_id': project_id,
        'auth_url': config.os_auth_url,
        'user_domain_id': 'default',
        'tenant_name': project_id, 'password': password,
        'project_domain_id': 'default'}

    request_session = requests.session()

    auth = auth_plugin.load_from_options(**params_no_version)
    session = osc_session.Session(
        auth=auth,
        session=request_session,
        verify=True)
    catalog = auth.get_auth_ref(session)['catalog']
    nova_catalog = [res for res in catalog
                    if res['type'] == 'compute'
                    and res['endpoints'][0]['region'] == region]
    neutron_catalog = [res for res in catalog
                       if res['type'] == 'network'
                       and res['endpoints'][0]['region'] == region]
    cinder_catalog = [res for res in catalog
                      if res['type'] == 'volumev2'
                      and res['endpoints'][0]['region'] == region]

    glance_catalog = [res for res in catalog
                      if res['type'] == 'image'
                      and res['endpoints'][0]['region'] == region]

    final_nova_catalog = []
    for res in nova_catalog:
        for r in res['endpoints']:
            if r['interface'] == 'public':
                final_nova_catalog.append(r['url'])

    final_neutron_catalog = []
    for res in neutron_catalog:
        for r in res['endpoints']:
            if r['interface'] == 'public':
                final_neutron_catalog.append(r['url'] + '/v2.0')

    final_cinder_catalog = []
    for res in cinder_catalog:
        for r in res['endpoints']:
            if r['interface'] == 'public':
                final_cinder_catalog.append(r['url'])

    final_glance_catalog = []
    for res in glance_catalog:
        for r in res['endpoints']:
            if r['interface'] == 'public':
                final_glance_catalog.append(r['url'])

    return (session.get_token(), final_nova_catalog,
            final_neutron_catalog, final_cinder_catalog,
            final_glance_catalog)


def commonfun(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        try:
            user_id = frequest.headers['user_id']
            password = frequest.headers['password']
            region = frequest.headers['region']
        except KeyError:
            msg = 'user_id, password and region must be provided'
            raise BadRequest(description=msg)
        try:
            user, project = _get_user_info(user_id)
        except AttributeError:
            msg = 'Invalid user %s: missing default_project_id' % user_id
            raise BadRequest(description=msg)
        except Exception as exc:
            raise BadRequest(description=exc.message)
        auth = login(user, project, password, region)
        return func(auth, region, *args, **kwargs)
    return wrap


def make_response(json_response, statu_code):
    return flask.make_response(
        flask.Response(json_response,
                       headers={'Content-Type':
                                'application/json'}),
        statu_code)


@keystonemod.route('/v3/services')
@commonfun
def get_service(auth, region):

    resp = httprequest.httpclient(
        'GET', config.os_auth_url + '/v3/services', auth[0])
    return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/resources')
@commonfun
def get_resources(auth, region):
    kwargs = {'headers': {'X-Openstack-Region': region}}
    resp = httprequest.httpclient(
        'GET', config.os_auth_url + '/v3/resources',
        auth[0], kwargs=kwargs)
    return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/projects', methods=['POST'])
@commonfun
def create_project(auth, region):
    json_body = json.loads(frequest.data)
    kwargs = {'json': json_body}
    resp = httprequest.httpclient(
        'POST', config.os_auth_url + '/v3/projects',
        auth[0], kwargs=kwargs)
    return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/projects/<project_id>', methods=['PATCH'])
@commonfun
def update_project(auth, region, project_id):
    json_body = json.loads(frequest.data)
    kwargs = {'json': json_body}
    resp = httprequest.httpclient(
        'PATCH', config.os_auth_url + '/v3/projects/%s' % project_id,
        auth[0], kwargs=kwargs)
    return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/projects/<project_id>', methods=['DELETE'])
@commonfun
def delete_project(auth, region, project_id):
    resp = httprequest.httpclient(
        'DELETE', config.os_auth_url + '/v3/projects/%s' % project_id,
        auth[0])
    if resp.status_code == 204:
        return make_response('', resp.status_code)
    else:
        return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/projects/<project_id>', methods=['GET'])
@commonfun
def get_project(auth, region, project_id):
    resp = httprequest.httpclient(
        'GET', config.os_auth_url + '/v3/projects/%s' % project_id,
        auth[0])
    return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/users', methods=['POST'])
@commonfun
def create_user(auth, region):
    json_body = json.loads(frequest.data)
    if 'default_project_id' not in json_body['user']:
        msg = 'default_project_id is needed when create user'
        raise BadRequest(description=msg)

    kwargs = {'json': json_body}
    resp = httprequest.httpclient(
        'POST', config.os_auth_url + '/v3/users',
        auth[0], kwargs=kwargs)
    resp_json = resp.json()
    if resp.status_code < 300:
        assignment_resp = httprequest.httpclient(
        'PUT', config.os_auth_url + '/v3/projects/%s/users/%s/roles/%s' % (
            json_body['user']['default_project_id'],
            resp_json['user']['id'], config.admin_role_id),
        auth[0])
        if assignment_resp.status_code > 300:
            resp = httprequest.httpclient(
            'DELETE', config.os_auth_url + '/v3/users/%s' % resp_json['user']['id'],
            auth[0])
            msg = 'Fail to create user'
            raise BadRequest(description=msg)

    return make_response(json.dumps(resp_json), resp.status_code)


@keystonemod.route('/v3/users/<user_id>', methods=['PATCH'])
@commonfun
def update_user(auth, region, user_id):
    json_body = json.loads(frequest.data)
    kwargs = {'json': json_body}
    resp = httprequest.httpclient(
        'PATCH', config.os_auth_url + '/v3/users/%s' % user_id,
        auth[0], kwargs=kwargs)
    return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/users/<user_id>', methods=['GET'])
@commonfun
def get_user(auth, region, user_id):
    resp = httprequest.httpclient(
        'GET', config.os_auth_url + '/v3/users/%s' % user_id,
        auth[0])
    return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/users/<user_id>', methods=['DELETE'])
@commonfun
def delete_user(auth, region, user_id):
    resp = httprequest.httpclient(
        'DELETE', config.os_auth_url + '/v3/users/%s' % user_id,
        auth[0])
    if resp.status_code == 204:
        return make_response('', resp.status_code)
    else:
        return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/<project_id>/quotas', methods=['GET'])
@commonfun
def get_quotas(auth, region, project_id):
    kwargs = {'headers': {'X-Openstack-Region': region}}
    resp = httprequest.httpclient(
        'GET', config.os_auth_url + '/v3/%s/quotas' % project_id,
        auth[0], kwargs=kwargs)
    return make_response(json.dumps(resp.json()), resp.status_code)


@keystonemod.route('/v3/<project_id>/quotas', methods=['PUT'])
@commonfun
def update_quotas(auth, region, project_id):
    json_body = json.loads(frequest.data)
    kwargs = {'headers': {'X-Openstack-Region': region}}
    kwargs['json'] = json_body
    resp = httprequest.httpclient(
        'PUT', config.os_auth_url + '/v3/%s/quotas' % project_id,
        auth[0], kwargs=kwargs)
    return make_response(json.dumps(resp.json()), resp.status_code)
