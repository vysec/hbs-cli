# -*- coding: utf-8 -*-
""" Work thread """

import threading
import time
import os
import subprocess

from subprocess import Popen, PIPE, check_output
from Registry import Registry
from libs.common import _d, file_lines_count, gen_random_md5, md5, new_db_connect


class ResultParseThread(threading.Thread):
    current_work_task_id = None
    daemon = True

    def __init__(self):
        threading.Thread.__init__(self)
        self._db = new_db_connect()

        config = Registry().get('config')
        self.tmp_dir = config['main']['tmp_dir']
        self.dicts_path = config['main']['dicts_path']
        self.outs_path = config['main']['outs_path']
        self.rules_path = config['main']['rules_path']
        self.path_to_hc = config['main']['path_to_hc']
        self.hc_bin = config['main']['hc_bin']

    def _update_status(self, status):
        self._update_work_task_field('status', status)

    def _get_work_task_data(self):
        return self._db.fetch_row("SELECT * FROM task_works WHERE id = {0}".format(self.current_work_task_id))

    def _update_work_task_field(self, field, value):
        self._db.update("task_works", {field: value}, "id = {0}".format(self.current_work_task_id))

    def run(self):
        while True:
            self.current_work_task_id = self._db.fetch_one(
                "SELECT id FROM task_works WHERE status='waitoutparse' ORDER BY id ASC LIMIT 1"
            )
            if self.current_work_task_id:
                _d("result_parser", "Getted result of task #{0}".format(self.current_work_task_id))
                self._update_status("outparsing")

                work_task = self._get_work_task_data()
                hashlist = self._db.fetch_row("SELECT * FROM hashlists WHERE id = {0}".format(work_task['hashlist_id']))

                if len(work_task['out_file']) and os.path.exists(work_task['out_file']):
                    _d("result_parser", "Start put found passwords info DB")

                    out_file_fh = open(work_task['out_file'], 'r')
                    for _line in out_file_fh:
                        _line = _line.strip()

                        password = _line[_line.rfind(":")+1:].strip().decode("hex")
                        summ = md5(_line[:_line.rfind(":")])

                        self._db.q(
                            "UPDATE `hashes` h, hashlists hl "
                            "SET `password` = {0}, cracked = 1 "
                            "WHERE h.hashlist_id = hl.id AND hl.alg_id = {1} AND h.summ = {2} AND !h.cracked"
                            .format(
                                self._db.quote(password),
                                hashlist['alg_id'],
                                self._db.quote(summ),
                            )
                        )



                    self._update_status('done')

                    os.remove(work_task['out_file'])
                    self._update_work_task_field('out_file', '')

                    self._db.q(
                        "UPDATE task_works SET uncracked_after = "
                        "(SELECT COUNT(id) FROM hashes WHERE hashlist_id = {0} AND !cracked) "
                        "WHERE id = {1}".format(work_task['hashlist_id'], work_task['id'])
                    )
                else:
                    _d("result_parser", "Outfile {0} not exists".format(work_task['out_file']))

                _d("result_parser", "Work for task #{0} done".format(self.current_work_task_id))

            self.current_work_task_id = None
            time.sleep(60)
        pass

