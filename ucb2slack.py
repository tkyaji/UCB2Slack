#!/usr/bin/python
# -*- coding: utf-8 -*-

###################################################
# Post to Slack, When Unity Cloud Build completes.
###################################################

import urllib
import urllib2
import json
import os
from ConfigParser import SafeConfigParser, NoOptionError, NoSectionError

# Output log only, if True
DEBUG=False

cdir = os.path.abspath(os.path.dirname(__file__))

# Version Log
ver_file = os.path.join(cdir, 'settings/ucb_vers.ini')
# Config
config_file = os.path.join(cdir, 'settings/projects.ini')


def load_config():
	configs = {}

	parser = SafeConfigParser()
	parser.read(config_file)

	option_keys = ('ucb_project_id', 'ucb_org_id', 'ucb_build_targets', 'ucb_api_key', 'slack_token', 'slack_channel', 'slack_username', 'slack_icon')

	for section in parser.sections():
		config_data = {}

		for option_key in option_keys:
			val = parser.get(section, option_key)
			config_data[option_key] = val

		configs[section] = config_data

	return configs


def get_current_version(project_name, build_target):
	parser = SafeConfigParser()
	parser.read(ver_file)
	try:
		return parser.getint(project_name, build_target)
	except NoSectionError:
		return 0
	except NoOptionError:
		return 0


def get_build_result(config, build_target):
	url_base = 'https://build-api.cloud.unity3d.com/api/v1/orgs/%s/projects/%s/buildtargets/%s/builds?per_page=1&page=1'
	url = url_base % (config['ucb_org_id'], config['ucb_project_id'], build_target)
	headers = {
		'Content-Type:' : 'application/json',
		'Authorization: Basic': config['ucb_api_key'],
	}

	req = urllib2.Request(url, None, headers)
	response = urllib2.urlopen(req)

	return json.loads(response.read())


def check_and_post(json_data_list, project_name, build_target, config, version):
	if len(json_data_list) == 0:
		return

	json_data_list.reverse()

	new_version = version
	for data in json_data_list:
		if data['build'] > version and data['buildStatus'] in ('success', 'failure'):
			post_to_slack(project_name, data, config)

			if data['build'] > new_version:
				new_version = int(data['build'])

	if not DEBUG and new_version > version:
		parser = SafeConfigParser()
		parser.read(ver_file)
		try:
			parser.set(project_name, build_target, str(new_version))
		except NoSectionError:
			parser.add_section(project_name)
			parser.set(project_name, build_target, str(new_version))
		parser.write(open(ver_file, 'w'))


def post_to_slack(project_name, data, config):
	url = 'https://slack.com/api/chat.postMessage'
	params = {
		'token' : config['slack_token'],
		'channel' : config['slack_channel'],
		'username' : config['slack_username'],
		'icon_url' : config['slack_icon'],
		'text' : get_post_text(project_name, data, config),
	}
	if DEBUG:
		print('### Slack Post Debug : %s ### ->' % project_name)
		print('[DATA]')
		print(data)
		print('[POST PARAM]')
		print(params)
		print('<- ###')
		return

	post_data = urllib.urlencode(params)
	req = urllib2.Request(url, post_data)
	response = urllib2.urlopen(req)
	print(data['buildTargetName'] + ' : ' + str(data['build']))


def get_post_text(project_name, data, config):
	text_list = []
	build_result = 'Succeeded' if data['buildStatus'] == 'success' else 'Failed'
	text_list.append('[%s] build %s : %s #%d' % (project_name, build_result, data['platform'].encode('utf_8'), data['build']))
	text_list.append('[ChangeLogs]')
	for change in data['changeset']:
		text_list.append('\t' + change['message'].encode('utf_8'))

	if data['buildStatus'] == 'success':
		text_list.append('[INSTALL]')
		url_base = 'https://build.cloud.unity3d.com/orgs/%s/projects/%s/buildtargets/%s/builds/%d/download/'
		download_url = url_base % (config['ucb_org_id'], config['ucb_project_id'], data['buildtargetid'].encode('utf_8'), data['build'])
		text_list.append('\t' + download_url)

	return '\r\n'.join(text_list)


if __name__ == '__main__':
	configs = load_config()
	for project_name, config in configs.items():
		build_targets = config['ucb_build_targets'].split(',')
		for build_target in build_targets:
			version = get_current_version(project_name, build_target)
			json_data_list = get_build_result(config, build_target)
			check_and_post(json_data_list, project_name, build_target, config, version)
