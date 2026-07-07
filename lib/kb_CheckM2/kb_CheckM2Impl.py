# -*- coding: utf-8 -*-
#BEGIN_HEADER
import os
import uuid
import logging
import subprocess
import glob
import shutil
import pandas as pd
from installed_clients.WorkspaceClient import Workspace
from installed_clients.DataFileUtilClient import DataFileUtil
from installed_clients.AssemblyUtilClient import AssemblyUtil
from installed_clients.GenomeFileUtilClient import GenomeFileUtil
from installed_clients.KBaseReportClient import KBaseReport
from installed_clients.MetagenomeUtilsClient import MetagenomeUtils
from lib.kb_CheckM2.Utils.OutputBuilder import OutputBuilder
#END_HEADER


class kb_CheckM2:

    VERSION = "0.0.2"
    GIT_URL = "https://github.com/Cyrus-Shahnam/kb_CheckM2.git"
    GIT_COMMIT_HASH = "6329fe6cc2a384c1d3be3ef3791bd342d97b3ae8"

    #BEGIN_CLASS_HEADER

    def _export_input_to_fastas(self, input_ref, obj_type):
        fasta_paths = []
        export_dir = os.path.join(self.scratch, 'fasta_' + uuid.uuid4().hex)
        os.makedirs(export_dir, exist_ok=True)

        if obj_type in ('KBaseGenomeAnnotations.Assembly',
                        'KBaseGenomes.ContigSet'):
            result = self.au.get_assembly_as_fasta({
                'ref': input_ref,
                'filename': os.path.join(export_dir, 'assembly.fasta')
            })
            fasta_paths.append(result['path'])

        elif obj_type == 'KBaseGenomes.Genome':
            result = self.gfu.genome_to_fasta({
                'genome_ref': input_ref,
                'is_gtdb_compliant': 0
            })
            fasta_paths.append(result['path_to_assembly'])

        elif obj_type in ('KBaseSets.AssemblySet',
                          'KBaseSearch.GenomeSet',
                          'KBaseGenomes.GenomeSet'):
            obj_data = self.ws.get_objects2(
                {'objects': [{'ref': input_ref}]}
            )['data'][0]['data']
            items = obj_data.get('items', obj_data.get('elements', []))
            for i, item in enumerate(items):
                ref = item.get('ref') or item
                sub_info = self.ws.get_object_info3(
                    {'objects': [{'ref': ref}]}
                )['infos'][0]
                sub_type = sub_info[2].split('-')[0]
                sub_fastas = self._export_input_to_fastas(ref, sub_type)
                fasta_paths.extend(sub_fastas)

        elif obj_type == 'KBaseMetagenomes.BinnedContigs':
            # Use MetagenomeUtils to export bins to FASTA files properly
            self.logger.info('Exporting BinnedContigs via MetagenomeUtils: %s', input_ref)
            result = self.mgu.binned_contigs_to_file({
                'input_ref': input_ref,
                'save_to_shock': 0
            })
            bin_dir = result['bin_file_directory']
            self.logger.info('Bins exported to directory: %s', bin_dir)

            for fname in os.listdir(bin_dir):
                if fname.endswith('.fasta') or fname.endswith('.fa') or fname.endswith('.fna'):
                    src = os.path.join(bin_dir, fname)
                    dst = os.path.join(export_dir, fname)
                    shutil.copy2(src, dst)
                    if os.path.getsize(dst) > 0:
                        fasta_paths.append(dst)
                        self.logger.info('Added bin: %s (%d bytes)',
                            fname, os.path.getsize(dst))
                    else:
                        self.logger.warning('Skipping empty bin: %s', fname)

            self.logger.info('Total non-empty bins: %d', len(fasta_paths))

        else:
            raise ValueError(
                'Unsupported object type: {}. Supported types: '
                'KBaseGenomeAnnotations.Assembly, KBaseGenomes.Genome, '
                'KBaseSets.AssemblySet, KBaseMetagenomes.BinnedContigs'.format(obj_type)
            )

        return fasta_paths

    def _run_checkm2(self, fasta_paths, params):
        out_dir = os.path.join(self.scratch, 'checkm2_' + uuid.uuid4().hex)
        os.makedirs(out_dir, exist_ok=True)

        input_dir = os.path.join(self.scratch, 'checkm2_input_' + uuid.uuid4().hex)
        os.makedirs(input_dir, exist_ok=True)

        for fasta in fasta_paths:
            basename = os.path.basename(fasta)
            if basename.endswith('.fasta.fasta'):
                basename = basename[:-len('.fasta')]
            dest = os.path.join(input_dir, basename)
            if not os.path.exists(dest):
                os.symlink(fasta, dest)

        threads = str(params.get('threads', 4))
        db_path = params.get('database_path') or self.checkm2_db

        cmd = [
            self.CHECKM2_BIN, 'predict',
            '--input', input_dir,
            '--output-directory', out_dir,
            '--threads', threads,
            '--database_path', db_path,
            '--extension', 'fasta',
            '--force',
        ]

        if params.get('lowmem'):
            cmd.append('--lowmem')

        if params.get('use_genes'):
            cmd.append('--genes')

        for k, v in (params.get('extra_options') or {}).items():
            cmd.extend(['--' + k, v])

        self.logger.info('Running CheckM2 command: %s', ' '.join(cmd))

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        self.logger.info('CheckM2 output:\n%s', result.stdout)

        if result.returncode != 0:
            raise ValueError(
                'CheckM2 failed (exit {}). Output:\n{}'.format(
                    result.returncode, result.stdout
                )
            )

        report_tsv = os.path.join(out_dir, 'quality_report.tsv')
        if not os.path.exists(report_tsv):
            raise ValueError(
                'CheckM2 ran but quality_report.tsv not found in: {}'.format(out_dir)
            )

        self.logger.info('CheckM2 completed. Output dir: %s', out_dir)
        return out_dir
    def _build_report_new(self, workspace_name, out_dir):
        pass
        outputBuilder = OutputBuilder(out_dir, self.scratch, self.callback_url)

    def _build_report(self, workspace_name, out_dir):
        report_tsv = os.path.join(out_dir, 'quality_report.tsv')

        #summary_lines = []
        #if os.path.exists(report_tsv):
            #with open(report_tsv, 'r') as f:
                #lines = f.readlines()
            #summary_lines = lines[:min(len(lines), 51)]

        message = 'CheckM2 quality assessment completed.\n\n'

        #message += 'Results summary:\n'
        #message += ''.join(summary_lines) if summary_lines else '(no results)'
        df = pd.read_csv(report_tsv, sep='\t')
        html_table = df.to_html(index=False)

        html_report = list()
        output_directory = os.path.join(self.shared_folder, str(uuid.uuid4()))
        os.mkdir(output_directory)
        result_file_path = os.path.join(output_directory, 'report.html')
        reportDirectory = "/kb/module/lib/kb_CheckM2/reports/"
        with open(result_file_path, 'w') as result_file:
            with open(os.path.join(reportDirectory, 'view_template.html'), 'r') as report_template_file:
                
                result_file.write(report_template_file.read().format(table=html_table))
        report_shock_id = self.dfu.file_to_shock({'file_path': output_directory,
                                                    'pack': 'zip'})['shock_id']
        html_report.append({'shock_id': report_shock_id,
                                'name': os.path.basename(result_file_path),
                                'label': os.path.basename(result_file_path),
                                'description': 'HTML summary report for CheckM2 quality assessment results'})
        file_links = []
        for fname in os.listdir(out_dir):
            fpath = os.path.join(out_dir, fname)
            if os.path.isfile(fpath):
                file_links.append({
                    'path': fpath,
                    'name': fname,
                    'label': fname,
                    'description': 'CheckM2 output: {}'.format(fname)
                })

        report_info = self.kbr.create_extended_report({
            'message': message,
            'html_links': html_report,
            'file_links': file_links,
            'html_window_height': 700,
            'workspace_name': workspace_name,
            'report_object_name': 'kb_CheckM2_report_' + uuid.uuid4().hex
        })

        return {
            'report_name': report_info['name'],
            'report_ref': report_info['ref'],
            'output_directory': out_dir
        }

    #END_CLASS_HEADER

    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        self.callback_url = os.environ.get('SDK_CALLBACK_URL')
        self.scratch = os.path.abspath(config['scratch'])
        self.ws_url = config['workspace-url']

        self.ws = Workspace(self.ws_url)
        self.dfu = DataFileUtil(self.callback_url)
        self.au = AssemblyUtil(self.callback_url)
        self.gfu = GenomeFileUtil(self.callback_url)
        self.kbr = KBaseReport(self.callback_url)
        self.mgu = MetagenomeUtils(self.callback_url)

        default_db = (
            config.get('checkm2_db')
            or os.environ.get('CHECKM2DB')
            or '/data/checkm2_db/CheckM2_database/CheckM2_database.dmnd'
        )
        if not os.path.exists(default_db):
            hits = glob.glob('/data/checkm2_db/**/*.dmnd', recursive=True)
            self.checkm2_db = hits[0] if hits else default_db
        else:
            self.checkm2_db = default_db

        self.CHECKM2_BIN = '/opt/conda/envs/checkm2/bin/checkm2'

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('kb_CheckM2')
        self.logger.info('Using CheckM2 database: %s', self.checkm2_db)
        #END_CONSTRUCTOR
        pass

    def run_checkm2_predict(self, ctx, params):
        """
        Run CheckM2 predict on the given input object and create a
        KBaseReport with the quality_report.tsv attached.
        """
        #BEGIN run_checkm2_predict
        self.logger.info('Starting run_checkm2_predict with params: %s', params)

        for required in ('workspace_name', 'input_ref'):
            if not params.get(required):
                raise ValueError('Parameter {} is required'.format(required))

        workspace_name = params['workspace_name']
        input_ref = params['input_ref']

        obj_info = self.ws.get_object_info3(
            {'objects': [{'ref': input_ref}]}
        )['infos'][0]
        obj_type = obj_info[2].split('-')[0]
        self.logger.info('Input object type: %s', obj_type)

        fasta_paths = self._export_input_to_fastas(input_ref, obj_type)
        if not fasta_paths:
            raise ValueError(
                'No FASTA files could be exported from input ref: {}'.format(input_ref)
            )
        self.logger.info('Exported %d FASTA file(s): %s', len(fasta_paths), fasta_paths)

        out_dir = self._run_checkm2(fasta_paths, params)
        result = self._build_report(workspace_name, out_dir)

        self.logger.info('run_checkm2_predict completed successfully')
        return [result]
        #END run_checkm2_predict

    def run_kb_CheckM2(self, ctx, params):
        """
        Alias method to match KBase naming convention.
        """
        #BEGIN run_kb_CheckM2
        return self.run_checkm2_predict(ctx, params)
    
        #END run_kb_CheckM2

    def status(self, ctx):
        #BEGIN_STATUS
        returnVal = {
            'state': 'OK',
            'message': '',
            'version': self.VERSION,
            'git_url': self.GIT_URL,
            'git_commit_hash': self.GIT_COMMIT_HASH
        }
        #END_STATUS
        return [returnVal]
