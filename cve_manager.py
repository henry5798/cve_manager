#!/usr/bin/python
#check out the ~/.pgpass file to store password securely and not in the source code (http://www.postgresql.org/docs/9.2/static/libpq-pgpass.html). libpq, the postgresql client librairy, check for this file to get proper login information.

import psycopg2
from psycopg2 import Error
from psycopg2 import connect
import sys
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import argparse
import os
from os import listdir
from os.path import isfile, join, exists
from os import makedirs
import argparse
import zipfile
import json
import requests
import re
import io 
import csv

##This is the Postgresql Database Schema##
query = '''
--
-- Name: cvss; Type: TABLE; Schema: public; Owner: atlas
--
CREATE TABLE public.cvss (
    cve character(20) NOT NULL,
    attack_complexity_3 character(5),
    attack_vector_3 character(20),
    availability_impact_3 character(5),
    confidentiality_impact_3 character(5),
    integrity_impact_3 character(5),
    privileges_required_3 character(5),
    scope_3 character(10),
    user_interaction_3 character(10),
    vector_string_3 character(50),
    exploitability_score_3 real,
    impact_score_3 real,
    base_score_3 real,
    base_severity_3 character(10),
    access_complexity character(10),
    access_vector character(20),
    authentication character(10),
    availability_impact character(10),
    confidentiality_impact character(10),
    integrity_impact character(10),
    obtain_all_privileges boolean,
    obtain_other_privileges boolean,
    obtain_user_privileges boolean,
    user_interaction_required boolean,
    vector_string character(50),
    exploitability_score real,
    impact_score real,
    base_score real,
    severity character(10),
    description text,
    published_date date,
    last_modified_date date
);
--ALTER TABLE public.cvss OWNER TO atlas;

--
-- Name: cpe; Type: TABLE; Schema: public; Owner: atlas
--
CREATE TABLE public.cpe (
    cve character(20) NOT NULL,
    cpe23uri text,
    vulnerable character(5)
);
--ALTER TABLE public.cpe OWNER TO atlas;

--
-- Name: cve_problem; Type: TABLE; Schema: public; Owner: atlas
--
CREATE TABLE public.cve_problem (
    cve character(20) NOT NULL,
    problem text
);
--ALTER TABLE public.cve_problem OWNER TO atlas;

--
-- Name: cvss_vs_cpes; Type: VIEW; Schema: public; Owner: atlas
--
CREATE VIEW public.cvss_vs_cpes AS
 SELECT cvss.cve,
    cvss.base_score_3,
    cvss.base_severity_3,
    cvss.base_score,
    cvss.severity,
    cpe.cpe23uri,
    cvss.description
   FROM public.cpe,
    public.cvss
  WHERE (cpe.cve = cvss.cve);
--ALTER TABLE public.cvss_vs_cpes OWNER TO atlas;
'''

## functions to manage the database (optional)
def create_database(myuser,mypassword,myhost,database, owner):
    con = None
    try:
        con = connect(dbname='postgres', user=myuser, host = myhost, password=mypassword)
        dbname = database
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        cur.execute('CREATE DATABASE ' + dbname)
        print("Database",database,"was created.")
        cur = con.cursor()
        query = '''ALTER DATABASE '''+ database + ''' OWNER TO ''' + owner+''';'''
        print("Owner of the database changed to:",owner) 
        cur.execute(query)
        con.commit()
    except (Exception, psycopg2.DatabaseError) as error :
        print("Error while creating PostgreSQL Database", error)
    finally:
        #closing database connection.
        if(con):
            cur.close()
            con.close()
            print("PostgreSQL connection is closed")

def drop_database(myuser,mypassword,myhost,database):
    con = None
    try:
        con = connect(dbname='postgres', user=myuser, host = myhost, password=mypassword)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        cur.execute('DROP DATABASE ' + database)
        print("Database",database,"was dropped.")
    except (Exception, psycopg2.DatabaseError) as error :
        print ("Error while dropping PostgreSQL Database", error)
    finally:
        #closing database connection.
        if(con):
            cur.close()
            con.close()
            print("PostgreSQL connection is closed")

def create_tables(myuser,mypassword,myhost,database):
    try:
        connection = None
        connection = connect(dbname=database, user=myuser, host = myhost, password=mypassword)
        cursor = connection.cursor()
        create_tables_query = query

        cursor.execute(create_tables_query)
        connection.commit()
        print("Tables and Views created successfully for database: "+database)
    except (Exception, psycopg2.DatabaseError) as error :
        print ("Error while creating PostgreSQL tables", error)
    finally:
        #closing database connection.
        if(connection):
            cursor.close()
            connection.close()
            print("PostgreSQL connection is closed")


#Download CVEs
def download_cves(directory,year):
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError:
            print ('Error: Creating directory. ' + directory)
            exit(0)
        else:  
            print ("Successfully created the directory %s" % directory)
    else:
        print ("Directory %s already exists" % directory)
    try:
        r = requests.get('https://nvd.nist.gov/vuln/data-feeds#JSON_FEED')
    except Exception as e:
        print(e)
    if year:
        print("downloading ",year," only")
        filename = "nvdcve-1.1-"+year+".json.zip"
        print(filename)
        r_file = requests.get("https://nvd.nist.gov/feeds/json/cve/1.1/" + filename, stream=True)
        with open(directory +"/" + filename, 'wb') as f:
            for chunk in r_file:
                f.write(chunk)
    else:
        for filename in re.findall("nvdcve-1.1-[0-9]*\.json\.zip",r.text):
            print(filename)
            r_file = requests.get("https://nvd.nist.gov/feeds/json/cve/1.1/" + filename, stream=True)
            with open(directory +"/" + filename, 'wb') as f:
                for chunk in r_file:
                    f.write(chunk)

#processes the already downloaded in json format CVEs
def process_cves(directory, results, csv_file, import_db,myuser,mypassword,myhost,database):
    if csv_file:
        if not os.path.exists(results):
            try:
                os.makedirs(results)
            except OSError:
                print ('Error: Creating directory. ' + results)
                exit(0)
            else:  
                print ("Successfully created the directory %s" % results)
        else:
            print ("Directory %s already exists" % results)

        file_cve_related_problems = open(results+"cve_related_problems.csv","w")
        writer_cwe=csv.writer(file_cve_related_problems,delimiter="\t")

        file_cvss_score = open(results+"cve_cvss_scores.csv","w")
        writer_cvss=csv.writer(file_cvss_score ,delimiter="\t")

        file_cpes = open(results+"cve_cpes.csv","w")
        writer_cpe=csv.writer(file_cpes,delimiter="\t")

        writer_cpe.writerow(["CVE","cpe23Uri","Vulnerable"])
        writer_cwe.writerow(["CVE","Problem"])
        writer_cvss.writerow(["CVE","Attack Complexity","Attack Vector","Availability Impact","Confidentiality Impact","Integrity Impact","Privileges Required","Scope","UserInteraction","Vector String","Exploitability Score","Impact Score","base Score","base Severity","Access Complexity","Access Vector","Authentication","Availability Impact","Confidentiality Impact","Integrity Impact","Obtain All Privilege","Obtain Other Privilege","Obtain User Privilege","User Interaction Required","Vector String","Exploitability Score","impact Score","baseScore","severity","Description","Published Date","Last Modified Date"])
        ########################################################################################
        all_cves = []
        directory = directory + "/"
        files = [f for f in listdir(directory) if isfile(join(directory, f))]
        files.sort(reverse=True)
        for file in files:
            print("\nProcessing", file)
            archive = zipfile.ZipFile(join(directory, file), 'r')
            jsonfile = archive.open(archive.namelist()[0])
            cve_dict = json.loads(jsonfile.read())
            print("CVE_data_timestamp: " + str(cve_dict['CVE_data_timestamp']))
            print("CVE_data_version: " + str(cve_dict['CVE_data_version']))
            print("CVE_data_format: " + str(cve_dict['CVE_data_format']))
            print("CVE_data_number of CVEs: " + str(cve_dict['CVE_data_numberOfCVEs']))
            print("CVE_data_type: " + str(cve_dict['CVE_data_type']))
            all_cves = all_cves + cve_dict['CVE_Items']
            #print(json.dumps(cve_dict['CVE_Items'][0], sort_keys=True, indent=4, separators=(',', ': ')))
            jsonfile.close()
        cvssv_score=[]
        for cves in all_cves:
            cve = cves['cve']['CVE_data_meta']['ID']
            description = ""
            for descriptions in cves['cve']['description']['description_data']:
                description = description + descriptions['value']
            try:
                writer_cvss.writerow([cve,cves['impact']['baseMetricV3']['cvssV3']['attackComplexity'],cves['impact']['baseMetricV3']['cvssV3']['attackVector'],cves['impact']['baseMetricV3']['cvssV3']['availabilityImpact'],cves['impact']['baseMetricV3']['cvssV3']['confidentialityImpact'],cves['impact']['baseMetricV3']['cvssV3']['integrityImpact'],cves['impact']['baseMetricV3']['cvssV3']['privilegesRequired'],cves['impact']['baseMetricV3']['cvssV3']['scope'],cves['impact']['baseMetricV3']['cvssV3']['userInteraction'],cves['impact']['baseMetricV3']['cvssV3']['vectorString'],str(cves['impact']['baseMetricV3']['exploitabilityScore']),str(cves['impact']['baseMetricV3']['impactScore']),str(cves['impact']['baseMetricV3']['cvssV3']['baseScore']),str(cves['impact']['baseMetricV3']['cvssV3']['baseSeverity']),cves['impact']['baseMetricV2']['cvssV2']['accessComplexity'],cves['impact']['baseMetricV2']['cvssV2']['accessVector'],cves['impact']['baseMetricV2']['cvssV2']['authentication'],cves['impact']['baseMetricV2']['cvssV2']['availabilityImpact'],cves['impact']['baseMetricV2']['cvssV2']['confidentialityImpact'],cves['impact']['baseMetricV2']['cvssV2']['integrityImpact'],str(cves['impact']['baseMetricV2']['obtainAllPrivilege']),str(cves['impact']['baseMetricV2']['obtainOtherPrivilege']),str(cves['impact']['baseMetricV2']['obtainUserPrivilege']),str(cves['impact']['baseMetricV2']['userInteractionRequired']),cves['impact']['baseMetricV2']['cvssV2']['vectorString'],str(cves['impact']['baseMetricV2']['exploitabilityScore']),str(cves['impact']['baseMetricV2']['impactScore']),str(cves['impact']['baseMetricV2']['cvssV2']['baseScore']),str(cves['impact']['baseMetricV2']['severity']),description,cves['publishedDate'],cves['lastModifiedDate']])
            except Exception as e:
                if str(e) == "'baseMetricV3'":
                    try:
                        writer_cvss.writerow([cve,None,None,None,None,None,None,None,None,None,None,None,None,None,cves['impact']['baseMetricV2']['cvssV2']['accessComplexity'],cves['impact']['baseMetricV2']['cvssV2']['accessVector'],cves['impact']['baseMetricV2']['cvssV2']['authentication'],cves['impact']['baseMetricV2']['cvssV2']['availabilityImpact'],cves['impact']['baseMetricV2']['cvssV2']['confidentialityImpact'],cves['impact']['baseMetricV2']['cvssV2']['integrityImpact'],str(cves['impact']['baseMetricV2']['obtainAllPrivilege']),str(cves['impact']['baseMetricV2']['obtainOtherPrivilege']),str(cves['impact']['baseMetricV2']['obtainUserPrivilege']),str(cves['impact']['baseMetricV2']['userInteractionRequired']),cves['impact']['baseMetricV2']['cvssV2']['vectorString'],str(cves['impact']['baseMetricV2']['exploitabilityScore']),str(cves['impact']['baseMetricV2']['impactScore']),str(cves['impact']['baseMetricV2']['cvssV2']['baseScore']),str(cves['impact']['baseMetricV2']['severity']),description,cves['publishedDate'],cves['lastModifiedDate']])
                    except Exception as e2:
                        if str(e2) == "'baseMetricV2'":
                            writer_cvss.writerow([cve,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,description,cves['publishedDate'],cves['lastModifiedDate']])
                        elif str(e2) == "'userInteractionRequired'":
                            writer_cvss.writerow([cve,None,None,None,None,None,None,None,None,None,None,None,None,None,cves['impact']['baseMetricV2']['cvssV2']['accessComplexity'],cves['impact']['baseMetricV2']['cvssV2']['accessVector'],cves['impact']['baseMetricV2']['cvssV2']['authentication'],cves['impact']['baseMetricV2']['cvssV2']['availabilityImpact'],cves['impact']['baseMetricV2']['cvssV2']['confidentialityImpact'],cves['impact']['baseMetricV2']['cvssV2']['integrityImpact'],str(cves['impact']['baseMetricV2']['obtainAllPrivilege']),str(cves['impact']['baseMetricV2']['obtainOtherPrivilege']),str(cves['impact']['baseMetricV2']['obtainUserPrivilege']),None,cves['impact']['baseMetricV2']['cvssV2']['vectorString'],str(cves['impact']['baseMetricV2']['exploitabilityScore']),str(cves['impact']['baseMetricV2']['impactScore']),str(cves['impact']['baseMetricV2']['cvssV2']['baseScore']),str(cves['impact']['baseMetricV2']['severity']),description,cves['publishedDate'],cves['lastModifiedDate']])
                        else:
                            print("Error e2",e2)
                elif str(e) == "'baseMetricV2'":
                    writer_cvss.writerow([cve,cves['impact']['baseMetricV3']['cvssV3']['attackComplexity'],cves['impact']['baseMetricV3']['cvssV3']['attackVector'],cves['impact']['baseMetricV3']['cvssV3']['availabilityImpact'],cves['impact']['baseMetricV3']['cvssV3']['confidentialityImpact'],cves['impact']['baseMetricV3']['cvssV3']['integrityImpact'],cves['impact']['baseMetricV3']['cvssV3']['privilegesRequired'],cves['impact']['baseMetricV3']['cvssV3']['scope'],cves['impact']['baseMetricV3']['cvssV3']['userInteraction'],cves['impact']['baseMetricV3']['cvssV3']['vectorString'],str(cves['impact']['baseMetricV3']['exploitabilityScore']),str(cves['impact']['baseMetricV3']['impactScore']),str(cves['impact']['baseMetricV3']['cvssV3']['baseScore']),str(cves['impact']['baseMetricV3']['cvssV3']['baseSeverity']),None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,description,cves['publishedDate'],cves['lastModifiedDate']])
                elif str(e) == "'userInteractionRequired'":
                    writer_cvss.writerow([cve,cves['impact']['baseMetricV3']['cvssV3']['attackComplexity'],cves['impact']['baseMetricV3']['cvssV3']['attackVector'],cves['impact']['baseMetricV3']['cvssV3']['availabilityImpact'],cves['impact']['baseMetricV3']['cvssV3']['confidentialityImpact'],cves['impact']['baseMetricV3']['cvssV3']['integrityImpact'],cves['impact']['baseMetricV3']['cvssV3']['privilegesRequired'],cves['impact']['baseMetricV3']['cvssV3']['scope'],cves['impact']['baseMetricV3']['cvssV3']['userInteraction'],cves['impact']['baseMetricV3']['cvssV3']['vectorString'],str(cves['impact']['baseMetricV3']['exploitabilityScore']),str(cves['impact']['baseMetricV3']['impactScore']),str(cves['impact']['baseMetricV3']['cvssV3']['baseScore']),str(cves['impact']['baseMetricV3']['cvssV3']['baseSeverity']),cves['impact']['baseMetricV2']['cvssV2']['accessComplexity'],cves['impact']['baseMetricV2']['cvssV2']['accessVector'],cves['impact']['baseMetricV2']['cvssV2']['authentication'],cves['impact']['baseMetricV2']['cvssV2']['availabilityImpact'],cves['impact']['baseMetricV2']['cvssV2']['confidentialityImpact'],cves['impact']['baseMetricV2']['cvssV2']['integrityImpact'],str(cves['impact']['baseMetricV2']['obtainAllPrivilege']),str(cves['impact']['baseMetricV2']['obtainOtherPrivilege']),str(cves['impact']['baseMetricV2']['obtainUserPrivilege']),None,cves['impact']['baseMetricV2']['cvssV2']['vectorString'],str(cves['impact']['baseMetricV2']['exploitabilityScore']),str(cves['impact']['baseMetricV2']['impactScore']),str(cves['impact']['baseMetricV2']['cvssV2']['baseScore']),str(cves['impact']['baseMetricV2']['severity']),description,cves['publishedDate'],cves['lastModifiedDate']])
                else:
                    print("Error e",e)

            for problem_type in cves['cve']['problemtype']['problemtype_data']:
                for descr in problem_type['description']:
                    problem =  descr['value']
                    if csv_file:
                        writer_cwe.writerow([cve,problem])
            try:
                cpe_list_length=len(cves['configurations']['nodes'])
                if (cpe_list_length !=0):
                    for i in range(0,cpe_list_length):
                        if 'children' in cves['configurations']['nodes'][i]:
                            cpe_child_list_length=len(cves['configurations']['nodes'][i]['children'])
                            if (cpe_child_list_length !=0):
                                for j in range(0,cpe_child_list_length):
                                    if('cpe_match' in cves['configurations']['nodes'][i]['children'][j]):
                                        cpes = cves['configurations']['nodes'][i]['children'][j]['cpe_match']
                                        for cpe in cpes:
                                            if csv_file:
                                                if 'cpe23Uri' in cpe:
                                                    writer_cpe.writerow([cve,cpe['cpe23Uri'],str(cpe['vulnerable'])])
                        else:
                            if('cpe_match' in cves['configurations']['nodes'][i]):
                                cpes = cves['configurations']['nodes'][i]['cpe_match']
                                for cpe in cpes:
                                    if csv_file:
                                        if 'cpe23Uri' in cpe:
                                            writer_cpe.writerow([cve,cpe['cpe23Uri'],str(cpe['vulnerable'])])
                            else:
                                cpe_inner_list_length=len(cves['configurations']['nodes'])
                                if (cpe_inner_list_length!=0):
                                    for k in range(0,cpe_inner_list_length):
                                        if('cpe_match' in cves['configurations']['nodes'][i]):
                                            cpes = cves['configurations']['nodes'][i]['cpe_match']
                                            for cpe in cpes:
                                                if csv_file:
                                                    if 'cpe23Uri' in cpe:
                                                        writer_cpe.writerow([cve,cpe['cpe23Uri'],str(cpe['vulnerable'])])
            except Exception as e:
                print(str(e),cves['configurations']) #check it
        file_cve_related_problems.close()
        file_cvss_score.close()
        file_cpes.close()
    if import_db:
        print('Connecting to the PostgreSQL database...')
        try:
            conn = psycopg2.connect("dbname='"+database+"' user='"+myuser+"' host='"+myhost+"' password='"+mypassword+"'")
        except psycopg2.Error as e:
            print( "I am unable to connect to the database. Error:",e)
            print( "Exiting")
            sys.exit(1)
        cur = conn.cursor()
        filename = results+"cve_cvss_scores.csv"
        with open(filename, 'r') as f:
            print("importing CVSS")
            filedata = f.read()
            filedata = filedata.replace("\\","\\\\")
            output = io.StringIO()
            output.write(filedata)
            output.seek(0)
            output.readline()
            cur.copy_from(output, 'cvss', sep='\t', null="")
        conn.commit()
        f.close()
        filename = results+"cve_related_problems.csv"
        with open(filename, 'r') as f:
            print("importing CVE-related problems")
            f.readline()
            cur.copy_from(f, 'cve_problem', sep='\t',columns=('cve', 'problem'))
        conn.commit()
        f.close()
        filename = results+"cve_cpes.csv"
        with open(filename, 'r') as f:
            print("importing CVEs vs CPEs")
            f.readline()
            cur.copy_from(f, 'cpe', sep='\t',columns=('cve','cpe23uri','vulnerable'))
            #cur.copy_from(f, 'cpe', sep='\t',columns=('cve','cpe22uri','cpe23uri','vulnerable'))
        conn.commit()
        f.close()

def truncate_database(myuser,mypassword,myhost,database):
    con = None
    try:
        con = connect(dbname=database, user=myuser, host = myhost, password=mypassword)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        print("Truncating CVEs tables")
        cur.execute("Truncate cpe, cve_problem, cvss;")
        con.commit()
    except (Exception, psycopg2.DatabaseError) as error :
        print("Error while Truncating PostgreSQL Database", error)
    finally:
        if(con):
            cur.close()
            con.close()
            print("PostgreSQL connection is closed")

def execute_query(myuser,mypassword,myhost,database,cve,score,date):
    con = None
    try:
        con = connect(dbname=database, user=myuser, host = myhost, password=mypassword)
        #con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        print("Executing query")
        if cve:
            cur.execute("SELECT cve, vector_string_3, base_score_3, base_severity_3, vector_string, base_score, severity, description, published_date FROM cvss WHERE cve LIKE '%"+cve+"%'")
            selected_cve = cur.fetchone()
            answer = ""
            for r in selected_cve:
                if type(r) is str:
                    answer = answer+r.strip()+"\t"
                else:
                    answer = answer+str(r)+"\t"
            answer = answer.rstrip('\t')
            print(answer)
    except (Exception, psycopg2.DatabaseError) as error :
        print ("Error while Querying Database", error)
    finally:
        if(con):
            cur.close()
            con.close()
            print("PostgreSQL connection is closed")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CVEs Manager.')
    parser.add_argument('-p', '--parse',  action="store_true", dest="process", default=False, help="Process downloaded CVEs.")
    parser.add_argument('-d', '--download',  action="store_true", dest="download", default=False, help="Download CVEs.")
    parser.add_argument('-y', '--year',  action="store", dest="year", default=False, help="The year for which CVEs shall be downloaded (e.g. 2019)")
    parser.add_argument('-csv', '--cvs_files',  action="store_true", dest="csv_file", default=False, help="Create CSVs files.")
    parser.add_argument('-idb', '--import_to_db',  action="store_true", dest="idb", default=False, help="Import CVEs into a database.")
    parser.add_argument('-i', '--input', action="store", default = 'nvd/', dest="input", help="The directory where NVD json files will been downloaded, and the one from where they will be parsed (default: nvd/")
    parser.add_argument('-o', '--output', action="store", default = 'results/', dest="results", help="The directory where the csv files will be stored (default: results/")
    parser.add_argument('-u', '--user',  action="store", dest="user", default="postgres", help="The user to connect to the database.")
    parser.add_argument('-ow', '--owner',  action="store", dest="owner", default=None, help="The owner of the database (if different from the connected user).")
    parser.add_argument('-ps', '--password',  action="store", dest="password", default="", help="The password to connect to the database.")
    parser.add_argument('-host', '--host',  action="store", dest="host", default="localhost", help="The host or IP of the database server.")
    parser.add_argument('-db', '--database',  action="store", dest="database", default="postgres", help="The name of the database.")
    parser.add_argument('-cd', '--create_database',  action="store_true", dest="cd", default=False, help="Create the database")
    parser.add_argument('-dd', '--drop_database',  action="store_true", dest="dd", default=False, help="Drop the database")
    parser.add_argument('-ct', '--create_tables',  action="store_true", dest="ct", default=False, help="Create the tables of the database")
    parser.add_argument('-tr', '--truncate_cves_tables',  action="store_true", dest="tr", default=False, help="Truncate the CVEs-related tables")
    parser.add_argument('-cve', '--cvs_number',  action="store", dest="cve", default=None, help="Print info for a CVE (CVSS score and other)")
    parser.add_argument('-sc', '--score',  action="store", dest="score", default=0.0, help="Use base score of a CVE as a selection criterion")
    parser.add_argument('-dt', '--date',  action="store", dest="date", default=1999, help="Use publication date of a CVE as a selection criterion")
    values = parser.parse_args()

    if not values.owner:
        values.owner=values.user
    if values.dd:
        drop_database(values.user,values.password,values.host,values.database)
    if values.cd:
        create_database(values.user,values.password,values.host,values.database,values.owner)
    if values.ct:
        create_tables(values.user,values.password,values.host,values.database)
    if values.download:
        download_cves(values.input,values.year)
    if values.process:
        process_cves(values.input, values.results, values.csv_file, values.idb,values.user,values.password,values.host,values.database)
    if values.tr: 
        truncate_database(values.user,values.password,values.host,values.database)
    if values.cve:
        execute_query(values.user,values.password,values.host,values.database,values.cve,values.score,values.date)
    if not values.input and not values.process and not values.dd and not values.cd and not values.ct and not values.download and not values.process and not values.tr and not values.cve:
        print("Choose an option (check --help)")
