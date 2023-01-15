from flask import Flask, jsonify, request
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

uri = os.getenv('URI')
user = os.getenv("USERNAMEDB")
password = os.getenv("PASSWORD")
driver = GraphDatabase.driver(uri, auth=(user, password), database="neo4j")


def get_workers(tx):
    args = request.args.to_dict()
    query = f"MATCH (e:Employee) RETURN e"

    if 'sort' in args.keys() and 'search' in args.keys():
        query = f"""MATCH (e:Employee) 
                    WHERE e.name CONTAINS '{args['search']}' 
                    OR e.surname CONTAINS '{args['search']}'
                    OR e.position CONTAINS '{args['search']}' 
                    RETURN e"""

        if args['sort'] in ['position', 'name', 'surname']:
            query += f" ORDER BY e.{args['sort']}"

    elif 'sort' in args.keys():

        if args['sort'] in ['position', 'name', 'surname']:
            query += f" ORDER BY e.{args['sort']}"

    elif 'search' in args.keys():
        query = f"""MATCH (e:Employee) 
                    WHERE e.name CONTAINS '{args['search']}' 
                    OR e.surname CONTAINS '{args['search']}'
                    OR e.position CONTAINS '{args['search']}' 
                    RETURN e"""

    results = tx.run(query).data()
    employees = [{'name': result['e']['name'], 'surname': result['e']['surname'],
                  'position': result['e']['position']} for result in results]

    return employees


@app.route('/employees', methods=["GET"])
def get_workers_route():
    with driver.session() as session:
        workers = session.execute_read(get_workers)
    response = {'workers': workers}
    return jsonify(response), 200


def add_worker(tx, name, surname, position, department, role):
    query = f"MATCH (m: Employee) WHERE m.name='{name}' AND m.surname='{surname}' RETURN m"
    results = tx.run(query).data()

    if not results:
        query1 = f"CREATE ({name}:Employee {{name:'{name}', surname:'{surname}', position:'{position}'}})"
        query2 = f"MATCH (a:Employee) WHERE a.name = '{name}' AND a.surname = '{surname}' MATCH (b:Department {{name: '{department}'}}) CREATE (a)-[r:WORKS_IN]->(b) RETURN type(r)"

        if (role == "worker"):
            tx.run(query1, name=name, surname=surname, position=position)
            tx.run(query2, name=name, surname=surname, department=department)
            return True
        else:
            query3 = f"MATCH (a:Employee),(b:Department) WHERE a.name = '{name}' AND a.surname = '{surname}' AND b.name = '{department}' CREATE (a)-[r:MANAGES]->(b) RETURN type(r)"

            tx.run(query1, name=name, surname=surname, position=position)
            tx.run(query2, name=name, surname=surname, department=department)
            tx.run(query3, name=name, surname=surname, department=department)
            return True

    else:
        return False


@app.route('/employees', methods=["POST"])
def add_worker_route():
    data = request.get_json()

    name = data['name']
    surname = data['surname']
    position = data['position']
    department = data['department']
    role = data['role']

    if (name == '' or surname == '' or position == '' or department == '' or role == ''):
        return jsonify("Complete your request"), 405

    with driver.session() as session:
        res = session.execute_write(
            add_worker, name, surname, position, department, role)

    if (res == False):
        return jsonify("Name and surname already exists in our db"), 400

    return jsonify("User has been added"), 200


def update_worker(tx, obj):
    query = f"MATCH (m:Employee)-[r]-(d:Department) WHERE ID(m) = {obj['id']} RETURN m, d, r"
    results = tx.run(query).data()

    if not results:
        return False

    else:
        query1 = f"MATCH (m: Employee) WHERE ID(m) = {obj['id']} SET m.name='{obj['name']}', m.surname='{obj['surname']}', m.position='{obj['position']}'"
        query2 = f"MATCH (m: Employee) WHERE ID(m) = {obj['id']} MATCH (m)-[r:WORKS_IN]->(d:Department {{name:'{results[0]['d']['name']}'}}) DELETE r"
        query3 = f"MATCH (m: Employee) WHERE ID(m) = {obj['id']} MATCH (m)-[r:MANAGES]->(d:Department {{name:'{results[0]['d']['name']}'}}) DELETE r"
        query4 = f"MATCH (a: Employee),(b:Department) WHERE ID(a) = {obj['id']} AND b.name = '{obj['department']}' CREATE (a)-[r:WORKS_IN]->(b) RETURN type(r)"
        if (obj['role'] == "worker"):
            tx.run(query1)
            tx.run(query2)
            tx.run(query3)
            tx.run(query4)
        else:
            query5 = f"MATCH (a: Employee),(b: Department) WHERE ID(a) = {obj['id']} AND b.name = '{obj['department']}' CREATE (a)-[r:MANAGES]->(b) RETURN type(r)"
            tx.run(query1)
            tx.run(query2)
            tx.run(query3)
            tx.run(query4)
            tx.run(query5)

        return True


@app.route("/employees/<string:id>", methods=["PUT"])
def update_worker_route(id):
    data = request.get_json()
    name = data['name']
    surname = data['surname']
    position = data['position']
    department = data['department']
    role = data['role']

    data['id'] = id

    if (name == '' or surname == '' or position == '' or department == '' or role == '' or id == ''):
        return jsonify("Complete your request"), 405

    with driver.session() as session:
        res = session.execute_write(
            update_worker, data)

    if (res == False):
        return jsonify("User not found"), 404

    return jsonify("User has been updated"), 200


def delete_worker(tx, id):
    query = f"MATCH (m:Employee)-[r]-(d:Department) WHERE ID(m) = {id} RETURN m, d, r"
    results = tx.run(query).data()

    if not results:
        return False

    else:
        query1 = f"MATCH (m: Employee) WHERE ID(m) = {id} DETACH DELETE m"
        tx.run(query1)

        return True


@app.route("/employees/<string:id>", methods=["DELETE"])
def delete_worker_route(id):
    with driver.session() as session:
        res = session.execute_write(
            delete_worker, id)

    if (res == False):
        return jsonify("User not found"), 404

    return jsonify("User has been deleted"), 200


def get_workers_suboordinates(tx, id):
    query = f"""MATCH (p:Employee), (p1:Employee) 
                WHERE ID(p1) = {id} MATCH (p1)-[r]-(d) 
               WHERE NOT (p)-[:MANAGES]-(:Department) 
               AND (p)-[:WORKS_IN]-(:Department {{name:d.name}}) 
               RETURN p"""
    results = tx.run(query).data()
    workers = [{'name': result['p']['name'],
               'surname': result['p']['surname']} for result in results]
    return workers


@app.route("/employees/<string:id>/subordinates", methods=["GET"])
def get_workers_suboordinates_route(id):
    with driver.session() as session:
        workers = session.read_transaction(get_workers_suboordinates, id)

    response = {'workers': workers}
    return jsonify(response), 200


def get_department_info(tx, id):
    query = f"""MATCH (e:Employee)-[r]->(d:Department)<-[:MANAGES]-(m:Employee)
                WHERE ID(e)={id}
                WITH d, m
                MATCH (es:Employee) -[r]-> (d)
                RETURN d, m, count(es) AS ces;
                """
    result = tx.run(query).data()[0]
    department = {'name': result['d']['name'],
                  'manager': result['m']['name'], 'employees': result['ces']}
    return department


@app.route('/employees/<string:id>/department', methods=['GET'])
def get_department_info_route(id):
    with driver.session() as session:
        department = session.execute_read(get_department_info, id)

    response = {'department': department}
    return jsonify(response), 200


def get_department_employees(tx, id):
    query = f"""MATCH (d:Department) 
                WHERE id(d) = {id} 
                RETURN d"""
    result = tx.run(query).data()

    if not result:
        return None

    else:
        query = f"""MATCH (d: Department)<-[r:WORKS_IN]-(e: Employee) 
                    WHERE id(d) = {id}
                    RETURN e"""
        results = tx.run(query).data()
        employees = [{'name': result['e']['name'],
                      'position': result['e']['position']} for result in results]
        return employees


@app.route('/departments/<id>/employees', methods=['GET'])
def get_department_employees_route(id):
    with driver.session() as session:
        employees = session.execute_read(get_department_employees, id)

    if not employees:
        return jsonify("Not found"), 404
    else:
        response = {'employees': employees}
        return jsonify(response), 200


def get_departments(tx):
    args = request.args.to_dict()
    query = f"MATCH (d: Department) RETURN d"

    if 'sort' in args.keys() and 'search' in args.keys():
        query = f"""MATCH (d: Department) 
                    WHERE d.name CONTAINS '{args['search']}' 
                    RETURN d"""

        if args['sort'] in ['name']:
            query += f" ORDER BY d.{args['sort']}"

    elif 'sort' in args.keys():

        if args['sort'] in ['name']:
            query += f" ORDER BY d.{args['sort']}"

    elif 'search' in args.keys():
        query = f"""MATCH (d: Department) 
                    WHERE d.name CONTAINS '{args['search']}' 
                    RETURN d"""

    results = tx.run(query).data()
    departments = [{'name': result['d']['name']} for result in results]

    return departments


@app.route('/departments', methods=['GET'])
def get_departments_route():
    with driver.session() as session:
        departments = session.execute_read(get_departments)
    response = {'departments': departments}
    return jsonify(response), 200


if __name__ == '__main__':
    app.run()
