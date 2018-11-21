#!/usr/bin/env python3

import argparse
import os.path
import re
import subprocess
import sys
import random

VERSIONS = {
    "dev-441": {
        "version": "indy1.3.1-dev-441-ew",
        "args": {
            "indy_sdk_repo": "https://github.com/bcgov/indy-sdk.git",
            "indy_sdk_rev": "574ca3a881d188c3fd7400d27acbe5edc4c7f666",
            "indy_crypto_repo": "https://github.com/hyperledger/indy-crypto.git",
            "indy_crypto_rev": "96c79b36c5056eade5a8e3bae418f5a733cc8d8d",
        }
    },
    "1.0": {
        "version": "1.0rc3",
        "args": {
            "indy_sdk_url": "https://codeload.github.com/ianco/indy-sdk/tar.gz/50ede4563a6a303b09d78ca97d3238e6c10333f6",
            "indy_crypto_url": "https://codeload.github.com/hyperledger/indy-crypto/tar.gz/96c79b36c5056eade5a8e3bae418f5a733cc8d8d",
        }
    },
    "1.0std": {
        "path": "1.0",
        "args": {
            "indy_sdk_url": "https://codeload.github.com/hyperledger/indy-sdk/tar.gz/e0ef8889e9f3b9abd706628fe259f56501d492d9",
            "indy_crypto_url": "https://codeload.github.com/hyperledger/indy-crypto/tar.gz/96c79b36c5056eade5a8e3bae418f5a733cc8d8d",
        }
    },
    "1.5": {
        "version": "1.5-0",
        "args": {
            "indy_sdk_url": "https://codeload.github.com/hyperledger/indy-sdk/tar.gz/16c637cbe855c46bf1d3a869e9ebcfc99bb9aabf",
            "indy_crypto_url": "https://codeload.github.com/hyperledger/indy-crypto/tar.gz/9586d6a24f53f2aa0621249f2266d0f129253c48",
        }
    },
    "1.6": {
        "version": "1.6-11",
        "args": {
            # 1.6.7
            "indy_sdk_url": "https://codeload.github.com/hyperledger/indy-sdk/tar.gz/5a37407baaf756b3c4f5cac802717dc4a2bd1660",
            # 0.4.5
            "indy_crypto_url": "https://codeload.github.com/hyperledger/indy-crypto/tar.gz/a2864642430064c6f00902e9b999cc6356eed9f1",
        }
    },
    "1.6-ew": {
        "version": "1.6-ew-11",
        "args": {
            # bcgov postgres_plugin branch
            "indy_sdk_url": "https://codeload.github.com/bcgov/indy-sdk/tar.gz/88424a10f53a7e47c49143b9866a0d531c1d9420",
            # 0.4.5
            "indy_crypto_url": "https://codeload.github.com/hyperledger/indy-crypto/tar.gz/a2864642430064c6f00902e9b999cc6356eed9f1",
        }
    }
}

DEFAULT_NAME = 'bcgovimages/von-image'
PY_35_VERSION = '3.5.5'
PY_36_VERSION = '3.6.7'


parser = argparse.ArgumentParser(description='Generate a von-image Docker image')
parser.add_argument('-n', '--name', default=DEFAULT_NAME, help='the base name for the docker image')
parser.add_argument('-t', '--tag', help='a custom tag for the docker image')
parser.add_argument('-f', '--file', help='use a custom Dockerfile')
parser.add_argument('--build-arg', metavar='ARG=VAL', action='append', help='add docker build arguments')
parser.add_argument('--debug', action='store_true', help='add docker build arguments')
parser.add_argument('--dry-run', action='store_true', help='print docker command line instead of executing')
parser.add_argument('--no-cache', action='store_true', help='ignore docker image cache')
parser.add_argument('-o', '--output', help='output an updated Dockerfile with the build arguments replaced')
parser.add_argument('--py35', dest='python', action='store_const', const=PY_35_VERSION, help='use the default python 3.5 version')
parser.add_argument('--py36', dest='python', action='store_const', const=PY_36_VERSION, help='use the default python 3.6 version')
parser.add_argument('--python', help='use a specific python version')
parser.add_argument('--push', action='store_true', help='push the resulting image')
parser.add_argument('-q', '--quiet', action='store_true', help='suppress output from docker build')
parser.add_argument('--release', dest='debug', action='store_false', help='produce a release build of libindy')
parser.add_argument('--s2i', action='store_true', help='build the s2i image for this version')
parser.add_argument('--squash', action='store_true', help='produce a smaller image')
parser.add_argument('--test', action='store_true', help='perform tests on docker image')
parser.add_argument('version', choices=VERSIONS.keys(), help='the predefined release version')

args = parser.parse_args()
ver = VERSIONS[args.version]
py_ver = args.python or ver.get('python_version', PY_35_VERSION)

target = ver.get('path', args.version)
dockerfile = target + '/Dockerfile.ubuntu'
if args.file:
    dockerfile = args.file

tag = args.tag
tag_name = args.name
if tag:
    tag_name, tag_version = tag.split(':', 2)
else:
    pfx = 'py' + py_ver[0:1] + py_ver[2:3] + '-'
    tag_version = pfx + ver.get('version', args.version)
    if args.debug:
        tag_version += '-debug'
    tag = tag_name + ':' + tag_version

build_args = {}
build_args.update(ver['args'])
build_args['python_version'] = py_ver
build_args['tag_name'] = tag_name
build_args['tag_version'] = tag_version
if not args.debug:
    build_args['indy_build_flags'] = '--release'
if args.build_arg:
    for arg in args.build_arg:
        key, val = arg.split('=', 2)
        build_args[key] = val

if args.output:
    src_path = dockerfile
    src_replace = build_args
    if args.test:
        src_path = target + '/Dockerfile.test'
        src_replace = {'base_image': tag}
    elif args.s2i:
        src_path = target + '/Dockerfile.s2i'
        src_replace = {'base_image': tag}
    with open(args.output, 'w') as out:
        with open(src_path) as src:
            for line in src:
                m = re.match(r'^ARG\s+(\w+)=?(.*)$', line)
                if m:
                    line = 'ARG {}={}\n'.format(m.group(1), src_replace.get(m.group(1), m.group(2)))
                out.write(line)
    sys.exit(0)

cmd_args = []
for k,v in build_args.items():
    cmd_args.extend(['--build-arg', '{}={}'.format(k,v)])
cmd_args_base = cmd_args.copy()
if dockerfile:
    cmd_args_base.extend(['-f', dockerfile + '_indy'])
    cmd_args.extend(['-f', dockerfile + '_von'])
if args.no_cache:
    cmd_args_base.append('--no-cache')
    cmd_args.append('--no-cache')
if args.squash:
    cmd_args_base.append('--squash')
    cmd_args.append('--squash')
cmd_args_base.extend(['-t', 'local_indy_base'])
cmd_args.extend(['-t', tag])
cmd_args.extend(['--build-arg', 'CACHEBUST=' + str(random.randint(100000,999999))])
cmd_args_base.append(target)
cmd_args.append(target)
cmd_base = ['docker', 'build'] + cmd_args_base
cmd = ['docker', 'build'] + cmd_args
if args.dry_run:
    print(' '.join(cmd))
else:
    print('Building docker image...')
    proc = subprocess.run(cmd_base, stdout=(subprocess.PIPE if args.quiet else None))
    if proc.returncode:
        print('build failed')
        sys.exit(1)
    proc = subprocess.run(cmd, stdout=(subprocess.PIPE if args.quiet else None))
    if proc.returncode:
        print('build failed')
        sys.exit(1)
    if args.quiet:
        print('Successfully tagged {}'.format(tag))
    proc_sz = subprocess.run(['docker', 'image', 'inspect', tag, '--format={{.Size}}'], stdout=subprocess.PIPE)
    size = int(proc_sz.stdout.decode('ascii').strip()) / 1024.0 / 1024.0
    print('%0.2f%s' % (size, 'MB'))

if args.s2i:
    s2i_tag = tag + '-s2i'
    s2i_cmd = [
        'docker', 'build', '--build-arg', 'base_image=' + tag, '-t', s2i_tag,
        '-f', target + '/Dockerfile.s2i', target
    ]
    if args.dry_run:
        print(' '.join(s2i_cmd))
    else:
        print(s2i_cmd)
        proc = subprocess.run(s2i_cmd, stdout=(subprocess.PIPE if args.quiet else None))
        if proc.returncode:
            print('s2i build failed')
            sys.exit(1)
        if args.quiet:
            print('Successfully tagged {}'.format(s2i_tag))

if not args.dry_run:
    if args.test or args.push:
        test_path = target + '/Dockerfile.test'
        test_tag = tag + '-test'
        proc_bt = subprocess.run(['docker', 'build', '--build-arg', 'base_image=' + tag,
                                  '-t', test_tag, '-f', test_path, target])
        if proc_bt.returncode:
            print('test image build failed')
            sys.exit(1)
        proc_test = subprocess.run(['docker', 'run', '--rm', '-i', test_tag])
        if proc_test.returncode:
            print('One or more tests failed')
            sys.exit(1)
        print('All tests passed')

    if args.push:
        print('Pushing docker image...')
        proc = subprocess.run(['docker', 'push', s2i_tag if args.s2i else tag])
        if proc.returncode:
            print('push failed')
            sys.exit(1)
