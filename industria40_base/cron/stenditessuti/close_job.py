# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import pdb
import pickle
import time
import erppeek
try:
    import ConfigParser
except:
    import configparser as ConfigParser

from datetime import datetime

# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
log_f = open('/tmp/I40_fabric_close_job.log', 'w')


def write_log(log_f, message, mode='INFO', verbose=True):
    """ Write log file
    """
    complete_message = '%s [%s]: %s' % (
        str(datetime.now())[:19],
        mode,
        message,
    )
    if verbose:
        print(' * {}'.format(complete_message))
    log_f.write('{}\n'.format(complete_message))
    log_f.flush()


# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
pickle_file = './file_status.log'
cfg_file = os.path.expanduser('./odoo.cfg')
config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')  # verify if it's necessary: getint

draft_path = os.path.expanduser(config.get('path', 'draft'))
cut_path = os.path.expanduser(config.get('path', 'cut'))

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
write_log(log_f, 'Connect to ODOO')
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
)
job_pool = odoo.model('industria.job')

try:
    file_status_log = pickle.load(open(pickle_file, 'rb'))
except:
    write_log(
        log_f, 'Creating pickle file: %s' % pickle_file)
    file_status_log = {}
pdb.set_trace()

for root, folders, files in os.walk(draft_path):
    for filename in files:
        fullname = os.path.join(root, filename)
        modify_time = os.stat(fullname).st_mtime
        # modify_time = time.ctime(os.stat(fullname[os.stat.ST_MTIME]))
        # <fileNameMattress>S:\unicont\Job_70217.fks</fileNameMattress>
        if file_status_log.get(fullname) != modify_time:
            no_error = True
            f_detail = open(fullname, 'r')
            write_log(log_f, 'Reading file %s' % fullname)
            for line in f_detail:
                if 'fileNameMattress' in line and 'Job_' in line:
                    job_id = int(line.split('_')[-1].split('.')[0])
                    try:
                        job_ids = job_pool.search([('id', '=', job_id)])
                        if not job_ids:
                            write_log(
                                log_f, 'Error no job %s present!' % job_id,
                                mode='ERROR')
                            # No error for file pickle!
                            continue

                        odoo_job = job_pool.browse(job_id)
                    except:
                        no_error = False
                        write_log(
                            log_f, 'Error no job %s present!' % job_id,
                            mode='ERROR')
                        continue
                    pdb.set_trace()
                    if odoo_job.state != 'COMPLETED':
                        try:
                            job_pool.completed_fabric_job([job_id])
                            write_log(
                                log_f, 'Close job %s' % job_id)
                        except:
                            no_error = False
                            write_log(
                                log_f, 'Error closing Job: %s' % job_id,
                                mode='ERROR')
            f_detail.close()

            if no_error:
                # No more read this file:
                file_status_log[fullname] = modify_time
                write_log(log_f, 'No more reading file for %s' % fullname)

# Store pickle information:
pickle.dump(
    file_status_log,
    open(pickle_file, 'wb'),
    )
