"""Functions for work with InterSystems IRIS"""

import json

try:
    import irisnative
except:
    pass


def get_iris(ip="localhost", port=1972, namespace="USER", username="_SYSTEM", password="SYS"):
    """Get IRIS object"""
    connection = irisnative.createConnection(ip, port, namespace, username, password)
    iris = irisnative.createIris(connection)
    return iris


def call(iris, class_name: str, method_name: str, args: list) -> object:
    """Call InterSystems IRIS classmethod"""
    args_copy = []

    for arg in args:
        args_copy.append(scalar_to_iris(iris, arg))

    returnvalue = iris.classMethodValue(class_name, method_name, *args_copy)
    if type(returnvalue).__name__ == 'IRISObject':
        returnvalue = object_to_string(returnvalue)

    try:
        returnvalue = json.loads(returnvalue)
    except Exception:
        pass

    return returnvalue


# Convert IRIS object to string
# Currently supports dynamic objects and streams
def object_to_string(obj):
    classname = obj.invokeString("%ClassName")
    if (classname == "%DynamicArray") or (classname == "%DynamicObject"):
        stream = obj._iris.classMethodObject("%Stream.TmpBinary", "%New")
        obj.invokeVoid("%ToJSON", stream)
        returnvalue = string_from_stream(stream)
    elif obj.invokeBoolean("%Extends", "%Stream.Object"):
        returnvalue = string_from_stream(obj)
    else:
        raise Exception(f"Unexpected result from a NativeAPI call. Got object of {classname} class.")

    return returnvalue


# Create IRIS stream from a string value, returns reference to the stream
def create_stream(iris, value):
    stream = iris.classMethodObject("%Stream.TmpBinary", "%New")
    chunk_size = 1000000
    for i in range(0, len(value), chunk_size):
        chunk = value[i:i + chunk_size]
        sc = stream.invokeBytes("Write", chunk)
        check_status(iris, sc)

    return stream


# Get python string from an IRIS stream
def string_from_stream(stream):
    stream.invokeVoid("Rewind")
    string = ""
    while not stream.getBoolean("AtEnd"):
        string += stream.invokeString("Read", 1000000)
    return string


# Create IRIS dynamic array from any iterable
def create_array(iris, array):
    iris_array = iris.classMethodObject("%DynamicArray", "%New")
    for value in array:
        iris_value = scalar_to_iris(iris, value)
        if (type(iris_value).__name__ == 'IRISObject') and iris_value.invokeBoolean("%Extends", "%Stream.Object"):
            iris_array.invokeVoid("%Push", iris_value, "stream")
        else:
            iris_array.invokeVoid("%Push", iris_value)
    return iris_array


# Create IRIS dynamic array from any subscriptable
def create_object(iris, obj):
    iris_obj = iris.classMethodObject("%DynamicObject", "%New")
    for key, value in obj.items():
        iris_value = scalar_to_iris(iris, value)
        if (type(iris_value).__name__ == 'IRISObject') and iris_value.invokeBoolean("%Extends", "%Stream.Object"):
            iris_obj.invokeVoid("%Set", key, iris_value, "stream")
        else:
            iris_obj.invokeVoid("%Set", key, iris_value)
    return iris_obj


# Recursively convert string, stream, list, tuple, dict to a corresponding IRIS object/scalar
def scalar_to_iris(iris, value):
    if (type(value) == str) and (len(value) >= 3641144):
        value = create_stream(iris, value)
    elif (type(value) == list) or (type(value) == tuple):
        value = create_array(iris, value)
    elif type(value) == dict:
        value = create_object(iris, value)

    return value


# If status is $$$OK nothing happens, otherwise raises an exception
def check_status(iris, sc, msg=""):
    is_ok = iris.classMethodBoolean("%SYSTEM.Status", "IsOK", sc)
    if is_ok:
        return

    error = iris.classMethodString("%SYSTEM.Status", "GetErrorText", sc)
    raise Exception(msg + " " + error)
