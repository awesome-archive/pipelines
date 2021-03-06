# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__all__ = [
    'load_component',
    'load_component_from_text',
    'load_component_from_url',
    'load_component_from_file',
]

import sys
from collections import OrderedDict
from ._yaml_utils import load_yaml
from ._structures import ComponentSpec
from ._structures import *


_default_component_name = 'Component'


def load_component(filename=None, url=None, text=None):
    '''
    Loads component from text, file or URL and creates a task factory function
    
    Only one argument should be specified.

    Args:
        filename: Path of local file containing the component definition.
        url: The URL of the component file data
        text: A string containing the component file data.

    Returns:
        A factory function with a strongly-typed signature.
        Once called with the required arguments, the factory constructs a pipeline task instance (ContainerOp).
    '''
    #This function should be called load_task_factory since it returns a factory function.
    #The real load_component function should produce an object with component properties (e.g. name, description, inputs/outputs).
    #TODO: Change this function to return component spec object but it should be callable to construct tasks.
    non_null_args_count = len([name for name, value in locals().items() if value != None])
    if non_null_args_count != 1:
        raise ValueError('Need to specify exactly one source')
    if filename:
        return load_component_from_file(filename)
    elif url:
        return load_component_from_url(url)
    elif text:
        return load_component_from_text(text)
    else:
        raise ValueError('Need to specify a source')


def load_component_from_url(url):
    '''
    Loads component from URL and creates a task factory function
    
    Args:
        url: The URL of the component file data

    Returns:
        A factory function with a strongly-typed signature.
        Once called with the required arguments, the factory constructs a pipeline task instance (ContainerOp).
    '''
    if url is None:
        raise TypeError
    import requests
    resp = requests.get(url)
    resp.raise_for_status()
    return _create_task_factory_from_component_text(resp.content, url)


def load_component_from_file(filename):
    '''
    Loads component from file and creates a task factory function
    
    Args:
        filename: Path of local file containing the component definition.

    Returns:
        A factory function with a strongly-typed signature.
        Once called with the required arguments, the factory constructs a pipeline task instance (ContainerOp).
    '''
    if filename is None:
        raise TypeError
    with open(filename, 'r') as yaml_file:
        return _create_task_factory_from_component_text(yaml_file, filename)


def load_component_from_text(text):
    '''
    Loads component from text and creates a task factory function
    
    Args:
        text: A string containing the component file data.

    Returns:
        A factory function with a strongly-typed signature.
        Once called with the required arguments, the factory constructs a pipeline task instance (ContainerOp).
    '''
    if text is None:
        raise TypeError
    return _create_task_factory_from_component_text(text, None)


def _create_task_factory_from_component_text(text_or_file, component_filename=None):
    component_dict = load_yaml(text_or_file)
    return _create_task_factory_from_component_dict(component_dict, component_filename)


def _create_task_factory_from_component_dict(component_dict, component_filename=None):
    component_spec = ComponentSpec.from_struct(component_dict)
    return _create_task_factory_from_component_spec(component_spec, component_filename)


def _normalize_identifier_name(name):
    import re
    normalized_name = name.lower()
    normalized_name = re.sub(r'[\W_]', ' ', normalized_name)           #No non-word characters
    normalized_name = re.sub(' +', ' ', normalized_name).strip()    #No double spaces, leading or trailing spaces
    if re.match(r'\d', normalized_name):
        normalized_name = 'n' + normalized_name                     #No leading digits
    return normalized_name


def _sanitize_kubernetes_resource_name(name):
    return _normalize_identifier_name(name).replace(' ', '-')


def _sanitize_python_function_name(name):
    return _normalize_identifier_name(name).replace(' ', '_')


def _sanitize_file_name(name):
    import re
    return re.sub('[^-_.0-9a-zA-Z]+', '_', name)


def _generate_unique_suffix(data):
    import time
    import hashlib
    string_data = str( (data, time.time()) )
    return hashlib.sha256(string_data.encode()).hexdigest()[0:8]

_inputs_dir = '/inputs'
_outputs_dir = '/outputs'
_single_io_file_name = 'data'


def _generate_input_file_name(port_name):
    return _inputs_dir + '/' + _sanitize_file_name(port_name) + '/' + _single_io_file_name


def _generate_output_file_name(port_name):
    return _outputs_dir + '/' + _sanitize_file_name(port_name) + '/' + _single_io_file_name


def _try_get_object_by_name(obj_name):
    '''Locates any Python object (type, module, function, global variable) by name'''
    try:
        ##Might be heavy since locate searches all Python modules
        #from pydoc import locate
        #return locate(obj_name) or obj_name
        import builtins
        return builtins.__dict__.get(obj_name, obj_name)
    except:
        pass
    return obj_name


def _make_name_unique_by_adding_index(name:str, collection, delimiter:str):
    unique_name = name
    if unique_name in collection:
        for i in range(2, sys.maxsize**10):
            unique_name = name + delimiter + str(i)
            if unique_name not in collection:
                break
    return unique_name


#Holds the transformation functions that are called each time TaskSpec instance is created from a component. If there are multiple handlers, the last one is used.
_created_task_transformation_handler = []


#TODO: Move to the dsl.Pipeline context class
from . import _dsl_bridge
_created_task_transformation_handler.append(_dsl_bridge.create_container_op_from_task)


#TODO: Refactor the function to make it shorter
def _create_task_factory_from_component_spec(component_spec:ComponentSpec, component_filename=None, component_ref: ComponentReference = None):
    name = component_spec.name or _default_component_name
    description = component_spec.description
    
    inputs_list = component_spec.inputs or [] #List[InputSpec]

    #Creating the name translation tables : Original <-> Pythonic 
    input_name_to_pythonic = {}
    pythonic_name_to_input_name = {}
    for io_port in inputs_list:
        pythonic_name = _sanitize_python_function_name(io_port.name)
        pythonic_name = _make_name_unique_by_adding_index(pythonic_name, pythonic_name_to_input_name, '_')
        input_name_to_pythonic[io_port.name] = pythonic_name
        pythonic_name_to_input_name[pythonic_name] = io_port.name

    if component_ref is None:
        component_ref = ComponentReference(name=component_spec.name or component_filename or _default_component_name)
    component_ref._component_spec = component_spec

    def create_task_from_component_and_arguments(pythonic_arguments):
        #Converting the argument names and not passing None arguments
        valid_argument_types = (str, int, float, bool, GraphInputArgument, TaskOutputArgument) #Hack for passed PipelineParams. TODO: Remove the hack once they're no longer passed here.
        arguments = {
            pythonic_name_to_input_name[k]: (v if isinstance(v, valid_argument_types) else str(v))
            for k, v in pythonic_arguments.items()
            if v is not None
        }
        task = TaskSpec(
            component_ref=component_ref,
            arguments=arguments,
        )
        if _created_task_transformation_handler:
            task = _created_task_transformation_handler[-1](task)
        return task

    import inspect
    from . import _dynamic

    #Reordering the inputs since in Python optional parameters must come after reuired parameters
    reordered_input_list = [input for input in inputs_list if not input.optional] + [input for input in inputs_list if input.optional]
    input_parameters  = [_dynamic.KwParameter(input_name_to_pythonic[port.name], annotation=(_try_get_object_by_name(str(port.type)) if port.type else inspect.Parameter.empty), default=(None if port.optional else inspect.Parameter.empty)) for port in reordered_input_list]
    factory_function_parameters = input_parameters #Outputs are no longer part of the task factory function signature. The paths are always generated by the system.
    
    return _dynamic.create_function_from_parameters(
        create_task_from_component_and_arguments,        
        factory_function_parameters,
        documentation=description,
        func_name=name,
        func_filename=component_filename
    )
