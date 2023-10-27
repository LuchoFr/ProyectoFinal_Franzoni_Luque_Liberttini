import mysql.connector
from flask_mysqldb import MySQL
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import jwt
import datetime
from functools import wraps
from flask_cors import CORS
from backend.product import Product
from backend.service import Service
from backend.client import Client


app = Flask(__name__)
CORS(app)

# Configura la conexión a la base de datos
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'user_api_final'
app.config['MYSQL_PASSWORD'] ='pass'
app.config['MYSQL_DB'] = 'db_proyecto_final'

#settings
app.config['SECRET_KEY'] = 'app_123'

mysql=MySQL(app)


#misma para verificar los tokens verificada
def token_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        print(kwargs)
        token = None

        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        
        if not token:
            return jsonify({"message": "Falta el token"}), 401
        
        user_id = None

        if 'user-id' in request.headers:
            user_id = request.headers['user-id']

        if not user_id:
            return jsonify({"message": "Falta el usuario"}), 401
        
        try:
            data = jwt.decode(token , app.config['SECRET_KEY'], algorithms = ['HS256'])
            token_id = data['id']

            if int(user_id) != int(token_id):
                return jsonify({"message": "Error de id"}), 401
            
        except Exception as e:
            print(e)
            return jsonify({"message": str(e)}), 401

        return func(*args, **kwargs)
    return decorated


def user_resources(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        print("Argumentos en user_resources: ", kwargs)
        id_user_route = kwargs['id']
        user_id = request.headers['user-id']
        if int(id_user_route) != int(user_id):
            return jsonify({"message": "No tiene permisos para acceder a este recurso"}), 401
        return func(*args, **kwargs)
    return decorated


#Esta tambien siempre va despues de def token_required(func)
#Esta se puede modificar para hacer con producto modificando solo la tabla 
#todas las rutas donde accedemos a un cliente por su id DELETE MODIFICAR
def client_resource(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        print("Argumentos en client_resource: ", kwargs)
        id_cliente = kwargs['id']
        cur = mysql.connection.cursor()
        cur.execute('SELECT userID FROM client WHERE id = {0}'.format(id_cliente)) 
        data = cur.fetchone()
        if data:
            id_prop = data[0]
            user_id = request.headers['user-id']
            if int(id_prop) != int(user_id):
                return jsonify({"message": "No tiene permisos para acceder a este recurso"}), 401
        return func(*args, **kwargs)
    return decorated


def pagina_no_encontrada(error):
    return '<h1> La Pagina que intentas acceder no existe. </h1>', 404


#actualizado con base de datos
@app.route('/login', methods=['POST'])
def loggin():
    auth = request.authorization
    
    # Comprueba si se proporcionó el usuario y la contraseña
    if not auth or not auth.username or not auth.password:
        return jsonify({"message": "No autorizado"}), 401

    # Consulta la base de datos para verificar el usuario y la contraseña
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE user = %s AND password = %s", (auth.username, auth.password))
    row = cur.fetchone()

    if not row:
        return jsonify({"message": "No autorizado"}), 401

    # En este punto, el usuario existe en la base de datos y la contraseña coincide
    token = jwt.encode({'id': row[0], 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=100), 'iss': 'your_iss_key'}, app.config["SECRET_KEY"])

    return jsonify({"token": token, "username": auth.username, "id": row[0]})



#VER COMENTARIOS DENTRO DE LA FUNCION
## GET PRODUCTOS BY USERID
@app.route('/users/<int:userID>/products', methods=['GET'])
@token_required
#@user_resources
def listar_productos(userID):
    #try:
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM products WHERE userID = {0}'.format(userID))
         #almacenamos una lista de productos
        data = cur.fetchall()
        print(data)
        #creo una lista para almacenar los productos q aextraigo de la BD
        productos = []
        for fila in data: #Objeto producto
            objProducto = Product(fila)
            productos.append(objProducto.to_json())

        return jsonify(productos)



#VER COMENTARIOS DENTRO DE LA FUNCION
## GET services BY ID USER
@app.route('/users/<int:userID>/services', methods=['GET'])
@token_required
#@user_resources
def listar_servicios(userID):
    #try:
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM services WHERE userID = {0}'.format(userID))
         #almacenamos una lista de servicios
        data = cur.fetchall()
        print(data)
        #creo una lista para almacenar los servicios q extraigo de la BD
        servicios = []
        for fila in data: #Objeto servicio
            objServicio = Service(fila)
            servicios.append(objServicio.to_json())

        return jsonify(servicios)



#POST PRODUCT 
@app.route('/users/<int:userID>/products', methods=['POST'])
@token_required
def create_product(userID):
    if request.method == 'POST':
        # Obtener los datos del JSON del request
        name = request.get_json()['name']
        description = request.get_json()['description']
        price = request.get_json()['price']
        stock = request.get_json()['stock']

        # Validar que los datos necesarios estén presentes
        if not name or not description or price is None or stock is None:
            return jsonify({"message": "Faltan datos requeridos"}), 400

        # Verificar si un producto con el mismo nombre ya existe
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM Products WHERE userID = %s AND name = %s', (userID, name))
        existing_product = cur.fetchone()
        cur.close()

        if existing_product:
            return jsonify({"message": "El producto con el mismo nombre ya existe para este usuario"}), 400

        # Crear una nueva entrada en la tabla 'Products' con el userID de la URL
        cur = mysql.connection.cursor()
        cur.execute('INSERT INTO Products (name, description, price, stock, userID) VALUES (%s, %s, %s, %s, %s)',
                    (name, description, price, stock, userID))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Producto creado exitosamente"}), 201



#SE MODIFICO PARA QUE SEA POR ID Y SE PUEDAN UPDATEAR TODOS LOS CAMPOS QUE SE QUIERAN
@app.route('/users/<int:userID>/products/<int:id>', methods=['PUT'])
@token_required
def update_product(userID, id):
    if request.method == 'PUT':

        # se obtienen los datos del JSON del request, si no esta se establece NONE
        name = request.get_json().get('name', None)
        description = request.get_json().get('description', None)
        price = request.get_json().get('price', None)
        stock = request.get_json().get('stock', None)

        # Validar que al menos uno de los campos a actualizar esté presente
        if not name and not description and price is None and stock is None:
            return jsonify({"message": "No se proporcionaron datos para actualizar"}), 400

        # Verificar si el producto a actualizar existe
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM Products WHERE userID = %s AND id = %s', (userID, id))

        #nos quedamos con uno
        existing_product = cur.fetchone()

        if not existing_product:
            cur.close()
            return jsonify({"message": "El producto no existe o no pertenece a este usuario"}), 404

        # diccionario con los campos apra actualizar
        updated_product = {}
        if name is not None:
            updated_product['name'] = name
        if description is not None:
            updated_product['description'] = description
        if price is not None:
            updated_product['price'] = price
        if stock is not None:
            updated_product['stock'] = stock

        # se actualiza el producto en la tabla 'Products' basado en el USERID y el ID DEL PRODUCTO
        cur.execute('UPDATE Products SET name = %s, description = %s, price = %s, stock = %s WHERE userID = %s AND id = %s',
                    (updated_product.get('name', existing_product[1]),
                     updated_product.get('description', existing_product[2]),
                     updated_product.get('price', existing_product[3]),
                     updated_product.get('stock', existing_product[4]),
                     userID,
                     id))
        
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Producto actualizado exitosamente"}), 200
    

#UPDATE STOCK 
@app.route('/products/update/stock', methods=['PUT'])
@token_required
def update_products():
    cur = mysql.connection.cursor()
    data = request.json.get('products')

    if not data:
        return jsonify({'message': 'Datos de productos no proporcionados'}), 400


    for product_data in data:
        product_id = product_data['id']

        # Actualiza los campos del producto con los valores proporcionados
        cur.execute(
            """
            UPDATE Products
            SET
                name = %s,
                description = %s,
                price = %s,
                stock = %s,
                userID = %s
            WHERE
                id = %s
            """,
            (
                product_data['name'],
                product_data['description'],
                product_data['price'],
                product_data['stock'],
                product_data['userID'],
                product_id
            )
        )
        mysql.connection.commit()
        return jsonify({"message": "Stock actualizado correctamente"}), 200


#UPDATE SERVICE
#SE MODIFICO PARA QUE SEA POR ID Y SE PUEDAN UPDATEAR TODOS LOS CAMPOS QUE SE QUIERAN
@app.route('/users/<int:userID>/services/<int:id>', methods=['PUT'])
@token_required
def update_service(userID, id):
    if request.method == 'PUT':

        # se obtienen los datos del JSON del request, si no esta se establece NONE
        name = request.get_json().get('name', None)
        description = request.get_json().get('description', None)
        price = request.get_json().get('price', None)

        # Validar que al menos uno de los campos a actualizar esté presente
        if not name and not description and price is None:
            return jsonify({"message": "No se proporcionaron datos para actualizar"}), 400

        # Verificar si el producto a actualizar existe
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM Services WHERE userID = %s AND id = %s', (userID, id))

        #nos quedamos con uno
        existing_service = cur.fetchone()

        if not existing_service:
            cur.close()
            return jsonify({"message": "El servicio no existe o no pertenece a este usuario"}), 404

        # diccionario con los campos para actualizar
        updated_service = {}
        if name is not None:
            updated_service['name'] = name
        if description is not None:
            updated_service['description'] = description
        if price is not None:
            updated_service['price'] = price


        # se actualiza el producto en la tabla 'Services' basado en el USERID y el ID DEL SERVICIO
        cur.execute('UPDATE Services SET name = %s, description = %s, price = %s WHERE userID = %s AND id = %s',
                    (updated_service.get('name', existing_service[1]),
                     updated_service.get('description', existing_service[2]),
                     updated_service.get('price', existing_service[3]),
                     userID,
                     id))
        
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Servicio actualizado exitosamente"}), 200



####DELETE PRODUCT
@app.route('/users/<int:userID>/products/<int:id>', methods=['DELETE'])
@token_required
def delete_product(userID, id):
    if request.method == 'DELETE':
        # Verificar si el producto a eliminar existe
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM Products WHERE userID = %s AND id = %s', (userID, id))
        existing_product = cur.fetchone()
        cur.close()

        if not existing_product:
            return jsonify({"message": "El producto no existe o no pertenece a este usuario"}), 404

        # Eliminar el producto de la tabla 'Products' basado en el nombre y el ID del usuario
        cur = mysql.connection.cursor()
        cur.execute('DELETE FROM Products WHERE userID = %s AND id = %s', (userID, id))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Producto eliminado exitosamente"}), 200


## GET clients BY ID USER
@app.route('/users/<int:userID>/clients', methods=['GET'])
@token_required
#@user_resources
def listar_clientes(userID):
    #try:
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM clients WHERE userID = {0}'.format(userID))
         #almacenamos una lista de clientes
        data = cur.fetchall()
        print(data)
        #creo una lista para almacenar los clientes q extraigo de la BD
        clientes = []
        for fila in data: #Objeto cliente
            objCliente = Client(fila)
            clientes.append(objCliente.to_json())

        return jsonify(clientes)
        

#POST CLIENT
@app.route('/users/<int:userID>/clients', methods=['POST'])
@token_required
def create_client(userID):
    if request.method == 'POST':
        # Obtener los datos del JSON del request
        name = request.get_json()['name']
        lastName = request.get_json()['lastName']
        address = request.get_json()['address']
        dni = request.get_json()['dni']
        cuit = request.get_json()['cuit']
        email = request.get_json()['email']

        # Validar que los datos necesarios estén presentes
        if not name or not lastName or address is None or dni is None or cuit is None or email is None:
            return jsonify({"message": "Faltan datos requeridos"}), 400

        # Verificar si un cliente con el mismo dni ya existe
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM Clients WHERE userID = %s AND email = %s', (userID, email))
        existing_client = cur.fetchone()
        cur.close()

        if existing_client:
            return jsonify({"message": "El cliente con el mismo email ya existe para este usuario"}), 400

        # Crear una nueva entrada en la tabla 'Clients' con el userID de la URL
        cur = mysql.connection.cursor()
        cur.execute('INSERT INTO Clients (name, lastName, address, dni, cuit, email, userID) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    (name, lastName, address, dni, cuit, email, userID))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Cliente creado exitosamente"}), 201


#UPDATE SERVICE
#SE MODIFICO PARA QUE SEA POR ID Y SE PUEDAN UPDATEAR TODOS LOS CAMPOS QUE SE QUIERAN
@app.route('/users/<int:userID>/clients/<int:id>', methods=['PUT'])
@token_required
def update_client(userID, id):
    if request.method == 'PUT':

        # se obtienen los datos del JSON del request, si no esta se establece NONE
        name = request.get_json().get('name', None)
        lastName = request.get_json().get('lastName', None)
        address = request.get_json().get('address', None)
        dni = request.get_json().get('dni', None)
        cuit = request.get_json().get('cuit', None)
        email = request.get_json().get('email', None)
        

        # Validar que al menos uno de los campos a actualizar esté presente
        if not name and not lastName and not address and not dni and not cuit and not email:
            return jsonify({"message": "No se proporcionaron datos para actualizar"}), 400


        # Verificar si el producto a actualizar existe
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM Clients WHERE userID = %s AND id = %s', (userID, id))

        #nos quedamos con uno
        existing_client = cur.fetchone()

        if not existing_client:
            cur.close()
            return jsonify({"message": "El cliente no existe o no pertenece a este usuario"}), 404

        # diccionario con los campos para actualizar
        updated_client = {}
        if name is not None:
            updated_client['name'] = name
        if lastName is not None:
            updated_client['lastName'] = lastName
        if address is not None:
            updated_client['address'] = address
        if dni is not None:
            updated_client['dni'] = dni
        if cuit is not None:
            updated_client['cuit'] = cuit
        if email is not None:
            updated_client['price'] = email


        # se actualiza el producto en la tabla 'Clients' basado en el USERID y el ID DEL CLIENTE
        cur.execute('UPDATE Clients SET name = %s, lastName = %s, address = %s, dni = %s, cuit = %s, email = %s WHERE userID = %s AND id = %s',
            (updated_client.get('name', existing_client[1]),
             updated_client.get('lastName', existing_client[2]),
             updated_client.get('address', existing_client[3]),
             updated_client.get('dni', existing_client[4]),
             updated_client.get('cuit', existing_client[5]),
             updated_client.get('email', existing_client[6]),
             userID,
             id))

        
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Cliente actualizado exitosamente"}), 200



####DELETE CLIENT
@app.route('/users/<int:userID>/clients/<int:id>', methods=['DELETE'])
@token_required
def delete_client(userID, id):
    if request.method == 'DELETE':
        # Verificar si el cliente a eliminar existe
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM Clients WHERE userID = %s AND id = %s', (userID, id))
        existing_client = cur.fetchone()
        cur.close()

        if not existing_client:
            return jsonify({"message": "El cliente no existe o no pertenece a este usuario"}), 404

        # Eliminar el producto de la tabla 'Products' basado en el nombre y el ID del usuario
        cur = mysql.connection.cursor()
        cur.execute('DELETE FROM Clients WHERE userID = %s AND id = %s', (userID, id))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Cliente eliminado exitosamente"}), 200
    
    
### METODOS PARA FACTURAS ###
@app.route('/bills', methods=['POST'])
@token_required
def agregar_factura():
    try:
        # Obtén los datos de la solicitud POST en formato JSON
        data = request.get_json()

        # Extrae los campos necesarios de los datos
        date = data['date']
        price = data['price']
        userID = data['userID']
        clientID = data['clientID']

        # Crea una nueva factura en la base de datos
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Bills (date, price, userID, clientID) VALUES (%s, %s, %s, %s)", (date, price, userID, clientID))
        mysql.connection.commit()
        cur.close()

        # Devuelve una respuesta de éxito
        response = jsonify({'message': 'Factura agregada con éxito'})
        response.status_code = 201  # Código HTTP 201 (Created)
        return response

    except Exception as e:
        # Si ocurre un error, devuelve un mensaje de error y un código HTTP 500 (Internal Server Error)
        response = jsonify({'error': str(e)})
        response.status_code = 500
        return response


if __name__ == '__main__':
    #configuraciones externas
    #un handler manejado por una funcion
    app.register_error_handler(404, pagina_no_encontrada)
    app.run(debug=True, port=4500)