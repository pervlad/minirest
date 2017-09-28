import inspect
import collections
import functools
import flask


class Api():
    '''Minimal REST API for flask
    Uses request handler function arguments as request http arguments trough application of annotations
    Automatic HTTP param validation
    Atomatic creation of documentation for REST APIs
    '''
    def __init__(self, app:flask.Flask, bad_request_fn:callable, 
                document_route='/api/docs/', type_validation=True, debug=False):
        self._app = app
        self.document_route = document_route
        self.type_validation = type_validation
        self.debug = debug
        self._docs = []
        self.bad_request_fn = bad_request_fn
        #  move this handler registration to ensure authorization and role check
        # self._app.route(self._document_route, methods=['GET']) (self._get_doc_json_req)
                                #    (lambda : flask.jsonify({'doc': self._docs}))
    def build_doc_data(self):
        # TODO debug invert should be used here to del certain attributes from dict copy...
        for req_doc in self._docs:
            try:
                req_doc['route'] = flask.current_app.config.get('SERVER_NAME', '') + req_doc['route']
            except KeyError:
                assert False, '"route" key must be present'
            if(not self.debug):
                try:
                    del req_doc['name']
                except KeyError:
                    assert False, '"name" key must be present'
        return self._docs
    
    def get_doc_json_req(self):
        '''REST doc request handler 
        
        Unfortunately flask.jsonify does not respect OrderedDict
        hence items are not in satisfying order.
        '''
        # it seems flask.jsonify does not respect ordered dict :(
        return flask.jsonify({'doc': self.build_doc_data()})
    
    def route(self, rule, **options):
        '''Adds additional functionality to standard Flask route decorator
        1. Uses function arguments to get REST API HTTP query parameters
        2. Performs validation based on type hints
        2. Collects and creates doc data for automatic JSON REST API documentation 
        '''
        def inner_dec(func):
            self._build_doc_dict(func, rule, **options)
            sig = inspect.signature(func)
            @functools.wraps(func)
            def wrap(*args, **kwargs):
                # TODO perform validation here too
                if(self.type_validation):
                    bpar = collections.OrderedDict()
                    for param in sig.parameters.values():
                        if(param.default is not param.empty):
                            v = flask.request.args.get(param.name, param.default)
                        else:
                            try:
                                v = flask.request.args[param.name]
                            except KeyError:
                                return self.bad_request_fn(
                                    'Validation Error.' + 
                                    ' Reqired HTTP parameter "{param.name}" is not present'.format(param=param)
                                )
                        try:
                            if(param.annotation is not sig.empty):
                                v = param.annotation(v) if v is not None else None
                        except (TypeError, ValueError):
                            return self.bad_request_fn('Validation Error.' + 
                                ' Invalid HTTP parameter "{param.name}" value "{param.value}"' + 
                                ' could not be converted to "{typ}"' \
                                .format(param=param, typ=param.annotation.__name__)
                            )
                        bpar[param.name] = v                      
                else:
                    bpar = collections.OrderedDict(
                        ((param.name, flask.request.args.get(param.name, param.default)) \
                        )
                    )
                ba = sig.bind(**bpar)
                return func(*ba.args, **ba.kwargs)
            # return wrap
            return self._app.route(rule, **options)(wrap)
        return inner_dec
    
    def _build_doc_dict(self, func, rule, **options):
        '''Creates API call documentation from function ignature'''
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return
        # print(name, sig)
        doc = collections.OrderedDict()
        doc['route'] = rule
        doc['method'] = options.get('methods', [])
        doc['name'] = func.__name__
        param_doc = []
        for param in sig.parameters.values():
            pdoc = {'name': param.name, 'type':param.annotation.__name__}
            if param.default is param.empty:
                pdoc['required'] = True
            else:
                pdoc['required'] = False
                pdoc['default'] = param.default

            param_doc.append(pdoc)
        doc['params'] = param_doc
        doc['doc'] = func.__doc__.strip()
        # print(doc)
        self._docs.append(doc)
        return doc   
