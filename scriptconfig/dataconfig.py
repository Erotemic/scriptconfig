"""
The new way to declare configurations.

Similar to the old-style Config objects, you simply declare a class that
inherits from :class:`scriptconfig.DataConfig` (or is wrapped by
:func:`scriptconfig.datconf`) and declare the class variables as the config
attributes much like you would write a dataclass.


Creating an instance of a ``DataConfig`` class works just like a regular
dataclass, and nothing special happens. You can create the argument parser by
using the :func:``DataConfig.cli`` classmethod, which works similarly to the
old-style :class:`scriptconfig.Config` constructor.

The following is the same top-level example as in :mod:`scriptconfig.config`,
but using ``DataConfig`` instead. It works as a drop-in replacement.


Example:
    >>> import scriptconfig as scfg
    >>> # In its simplest incarnation, the config class specifies default values.
    >>> # For each configuration parameter.
    >>> class ExampleConfig(scfg.DataConfig):
    >>>      num = 1
    >>>      mode = 'bar'
    >>>      ignore = ['baz', 'biz']
    >>> # Creating an instance, starts using the defaults
    >>> config = ExampleConfig()
    >>> # Typically you will want to update default from a dict or file.  By
    >>> # specifying cmdline=True you denote that it is ok for the contents of
    >>> # `sys.argv` to override config values. Here we pass a dict to `load`.
    >>> kwargs = {'num': 2}
    >>> config.load(kwargs, cmdline=False)
    >>> assert config['num'] == 2
    >>> # The `load` method can also be passed a json/yaml file/path.
    >>> import tempfile
    >>> config_fpath = tempfile.mktemp()
    >>> open(config_fpath, 'w').write('{"num": 3}')
    >>> config.load(config_fpath, cmdline=False)
    >>> assert config['num'] == 3
    >>> # It is possible to load only from CLI by setting cmdline=True
    >>> # or by setting it to a custom sys.argv
    >>> config.load(cmdline=['--num=4', '--mode' ,'fiz'])
    >>> assert config['num'] == 4
    >>> assert config['mode'] == 'fiz'
    >>> # You can also just use the command line string itself
    >>> config.load(cmdline='--num=4 --mode fiz')
    >>> assert config['num'] == 4
    >>> assert config['mode'] == 'fiz'
    >>> # Note that using `config.load(cmdline=True)` will just use the
    >>> # contents of sys.argv

Notes:
    https://docs.python.org/3/library/dataclasses.html
"""
from collections import OrderedDict
from scriptconfig.config import Config, MetaConfig
from scriptconfig.value import Value
import inspect
import warnings
import ubelt as ub
from scriptconfig import diagnostics
from scriptconfig.subconfig import (
    SubConfig,
    apply_dot_updates,
    class_has_subconfigs,
    coerce_argv,
    coerce_data_updates,
    config_to_nested_dict,
    ensure_subconfigs_instantiated,
    extract_selector_overrides,
    finalize_post_init,
    handle_special_dump,
    _FlatConfig,
    scan_config_path,
    wrap_subconfig_defaults,
)


__all__ = ['dataconf', 'DataConfig', 'MetaDataConfig', 'SubConfig']


def dataconf(cls):
    """
    Aims to be similar to the dataclass decorator

    Note:
        It is currently recommended to extend from the :class:`DataConfig`
        object instead of decorating with ``@dataconf``. These have slightly
        different behaviors and the former is more well-tested.

    Example:
        >>> from scriptconfig.dataconfig import *  # NOQA
        >>> import scriptconfig as scfg
        >>> @dataconf
        >>> class ExampleDataConfig2:
        >>>     chip_dims = scfg.Value((256, 256), help='chip size')
        >>>     time_dim = scfg.Value(3, help='number of time steps')
        >>>     channels = scfg.Value('*:(red|green|blue)', help='sensor / channel code')
        >>>     time_sampling = scfg.Value('soft2')
        >>> cls = ExampleDataConfig2
        >>> print(f'cls={cls}')
        >>> self = cls()
        >>> print(f'self={self}')

    Example:
        >>> from scriptconfig.dataconfig import *  # NOQA
        >>> import scriptconfig as scfg
        >>> @dataconf
        >>> class PathologicalConfig:
        >>>     default0 = scfg.Value((256, 256), help='chip size')
        >>>     default = scfg.Value((256, 256), help='chip size')
        >>>     keys = [1, 2, 3]
        >>>     __default__ = {
        >>>         'argparse': 3.3,
        >>>         'keys': [4, 5],
        >>>     }
        >>>     default = None
        >>>     time_sampling = scfg.Value('soft2')
        >>>     def foobar(self):
        >>>         ...
        >>> self = PathologicalConfig(1, 2, 3)
        >>> print(f'self={self}')

    # FIXME: xdoctest problem. Need to be able to simulate a module global scope
    # Example:
    #     >>> # Using inheritance and the decorator lets you pickle the object
    #     >>> from scriptconfig.dataconfig import *  # NOQA
    #     >>> import scriptconfig as scfg
    #     >>> @dataconf
    #     >>> class PathologicalConfig2(scfg.DataConfig):
    #     >>>     default0 = scfg.Value((256, 256), help='chip size')
    #     >>>     default2 = scfg.Value((256, 256), help='chip size')
    #     >>>     #keys = [1, 2, 3] : Too much
    #     >>>     __default__3 = {
    #     >>>         'argparse': 3.3,
    #     >>>         'keys2': [4, 5],
    #     >>>     }
    #     >>>     default2 = None
    #     >>>     time_sampling = scfg.Value('soft2')
    #     >>> config = PathologicalConfig2()
    #     >>> import pickle
    #     >>> serial = pickle.dumps(config)
    #     >>> recon = pickle.loads(serial)
    #     >>> assert 'locals' not in str(PathologicalConfig2)

    """
    # if not dataclasses.is_dataclass(cls):
    #     dcls = dataclasses.dataclass(cls)
    # else:
    #     dcls = cls

    # fields = dataclasses.fields(cls)
    # for field in fields:
    #     field.type
    #     field.name
    #     field.default

    if getattr(cls, '__did_dataconfig_init__', False):
        # The metaclass took care of this.
        # TODO: let the metaclass take care of most everything.
        return cls

    attr_default = {}
    for k, v in vars(cls).items():
        if not k.startswith('_') and not callable(v) and not isinstance(v, classmethod) and not isinstance(v, staticmethod):
            attr_default[k] = v
    default = attr_default.copy()
    cls_default = getattr(cls, '__default__', None)
    if cls_default is None:
        cls_default = {}
    default.update(cls_default)

    if issubclass(cls, DataConfig):
        # Helps make the class pickleable. Pretty hacky though.
        # TODO: Remove. This should no longer be necessary. Given the metaclass.
        SubConfig = cls
        SubConfig.__default__ = default
        for k in attr_default:
            delattr(SubConfig, k)
    else:
        # dynamic subclass, this has issues with pickle It would be nice if we
        # could improve this. There must be a way that dataclasses does it that
        # we could follow.
        class SubConfig(DataConfig):
            __doc__ = getattr(cls, '__doc__', {})
            __name__ = getattr(cls, '__name__', {})
            __default__ = default
            __description__ = getattr(cls, '__description__', {})
            __epilog__ = getattr(cls, '__epilog__', {})
            __qualname__ = cls.__qualname__
            __module__ = cls.__module__
    return SubConfig


class MetaDataConfig(MetaConfig):
    """
    This metaclass allows us to call `dataconf` when a new subclass is defined
    without the extra boilerplate.
    """
    @staticmethod
    def __new__(mcls, name, bases, namespace, *args, **kwargs):
        # Defining a new class that inherits from DataConfig
        if diagnostics.DEBUG_META_DATA_CONFIG:
            print(f'MetaDataConfig.__new__ called: {mcls=} {name=} {bases=} {namespace=} {args=} {kwargs=}')

        # Only do this for children of DataConfig, skip this for DataConfig
        # itself. This is a hacky way to do this. Can we make this check more
        # robust? The problem is the `DataConfig` attribute isn't defined when
        # this runs, so we can't check for equality to it, otherwise we could
        # just check that bases included `DataConfig`.
        if namespace.get('__module__', None) != 'scriptconfig.dataconfig' or name != 'DataConfig':
            # Cant call datconf directly, but we can simulate
            # We can modify the namespace before the class gets constructed
            # too, which is slightly cleaner.
            attr_default = {}
            for k, v in namespace.items():
                if not k.startswith('_') and not callable(v) and not isinstance(v, classmethod) and not isinstance(v, staticmethod):
                    attr_default[k] = v
            this_default = attr_default.copy()
            cls_default = namespace.get('__default__', None)
            if cls_default is None:
                cls_default = {}

            this_default.update(cls_default)

            if '__class__' in this_default:
                raise ValueError('The name "__class__" is reserved for nested DataConfig meta keys')
            # Helps make the class pickleable. Pretty hacky though.
            for k in attr_default:
                namespace.pop(k)
            namespace['__default__'] = this_default
            # print(f'this_default={this_default}')
            namespace['__did_dataconfig_init__'] = True

            for k, v in this_default.items():
                if isinstance(v, tuple) and len(v) == 1 and isinstance(v[0], Value):
                    warnings.warn(ub.paragraph(
                        f'''
                        It looks like you have a trailing comma in your
                        {name} DataConfig.  The variable {k!r} has a value of
                        {v!r}, which is a Tuple[Value]. Typically it should be
                        a Value.
                        '''), UserWarning)
        cls = super().__new__(mcls, name, bases, namespace, *args, **kwargs)

        # Modify the docstring to include information about the defaults
        if cls.__init__.__doc__ == '__autogenerateme__':
            valid_keys = list(cls.__default__.keys())
            cls.__init__.__doc__ = ub.codeblock(
                f'''
                Valid options: {valid_keys}

                Args:
                    *args: positional arguments for this data config
                    **kwargs: keyword arguments for this data config
                ''')
        return cls


class DataConfig(Config, metaclass=MetaDataConfig):
    """
    Base class for dataconfig-style configs.
    Overwrite this docstr with a description.

    To use, create a class (e.g. MyConfig) that inherits from DataConfig.  The
    configuration keys and their default values are specified by class level
    attributes. Metadata for keys can be given by specifying the default values
    as a :class:`scriptconfig.Value`.

    An instance can be created programmatically with keyword arguments
    specifying updates to default values.

    The :func:`DataConfig.cli` classmethod can be used to create an instance
    where the values are optionally populated from command line arguments in
    ``sys.argv`` or a custom ``argv``.

    Usage of the config is flexible.  It can be used as a dictionary or as a
    namespace. That is, you can either use ``config['key']`` or ``config.key``
    to access values for ``key``. The only incompatibility between this and a
    normal dictionary is that this does not allow new keys to be added,
    otherwise it can be treated exactly as a dictionary.

    Example:
        >>> import scriptconfig as scfg
        >>> class MyConfig(scfg.DataConfig):
        >>>     key1 = 'default-value1'
        >>>     key2 = 'default-value2'
        >>>     key3 = scfg.Value('default-value3', help='extra metadata!')
        >>> # Create a programmatic instance
        >>> config = MyConfig()
        >>> print(f'config={config}')
        config=<MyConfig({'key1': 'default-value1', 'key2': 'default-value2', 'key3': 'default-value3'})>
        >>> # Create an instance via command line args
        >>> # (note the default "smartcasting")
        >>> config = MyConfig.cli(argv=['--key1', '123', '--key2=345', '--key3=abc'])
        >>> print(f'config={config}')
        config=<MyConfig({'key1': 123, 'key2': 345, 'key3': 'abc'})>

    For fine-grained control overwrite the following attributes:

        * ``__epilog__`` (str):  documentation for the epilog of the argparse help string

        * ``__post_init__`` (callable): function that normalizes values on instance creation.

        * ``__default__`` (Dict[str, Any]): an alternate way to specify key/default-values based on an existing dictionary. Specifying an item in this dictionary has the same effect as specifying a class-attribute.

    SeeAlso:
        :class:`scriptconfig.Config`
    """
    # Not sure if having a docstring for this will break user-configs.
    # No docstring, because user-specified docstring will define the default
    # __description__.
    __default__ = None
    __description__ = None
    __epilog__ = None

    def __init__(self, *args, **kwargs):
        "__autogenerateme__"
        # Private internal hack to prevent __post_init__ from being called
        # if we are immediately going to load and call it again.
        _dont_call_post_init = kwargs.pop('_dont_call_post_init', False)

        self._data = None
        self._default = OrderedDict()
        if getattr(self, '__default__', None):
            # allow for class attributes to specify the default
            self._default.update(self.__default__)
        argkeys = list(self._default.keys())[0:len(args)]
        new_defaults = ub.dzip(argkeys, args)
        kwargs = self._normalize_alias_dict(kwargs)
        new_defaults.update(kwargs)
        unknown_args = ub.dict_diff(new_defaults, self._default)
        if unknown_args:
            raise ValueError((
                "Unknown Arguments: {}. Expected arguments are: {}"
            ).format(unknown_args, list(self._default)))
        self._default.update(new_defaults)
        self._data = self._default.copy()
        self._subconfig_meta = {}
        self._has_subconfigs = False
        wrap_subconfig_defaults(self, _dont_call_post_init=_dont_call_post_init)
        self._enable_setattr = True
        self._scfg_post_init_done = False
        if not _dont_call_post_init:
            self.__post_init__()
            self._scfg_post_init_done = True

    def __getattr__(self, key):
        # Note: attributes that mirror the public API will be suppressed
        # It is generally better to use the dictionary interface instead
        # But we want this to be data-classy, so...
        if key.startswith('_'):
            # config vars must not start with '_'. That is only for us
            raise AttributeError(key)
        if key in self:
            try:
                return self[key]
            except KeyError:
                raise AttributeError(key)
        raise AttributeError(key)

    def __dir__(self):
        initial = super().__dir__()
        return initial + list(self.keys())

    def __setattr__(self, key, value):
        """
        Forwards setattrs in the configuration to the dictionary interface,
        otherwise passes it through.
        """
        if key.startswith('_'):
            # Currently we do not allow leading underscores to be config
            # values to give us some flexibility for API changes.
            self.__dict__[key] = value
        else:
            can_setattr = (getattr(self, '__allow_newattr__', False))  # case where user can add new keys on the fly
            can_setattr |= (getattr(self, '_enable_setattr', False) and key in self)  # internal usage for initialization
            if can_setattr:
                # After object initialization allow the user to use setattr on any
                # value in the underlying dictionary. Everything else uses the
                # normal mechanism.
                try:
                    self[key] = value
                except KeyError:
                    raise AttributeError(key)
            else:
                self.__dict__[key] = value

    @classmethod
    def legacy(cls, cmdline=False, data=None, default=None, strict=False):
        """
        Calls the original "load" way of creating non-dataclass config objects.
        This may be refactored in the future.
        """
        import ubelt as ub
        ub.schedule_deprecation(
            'scriptconfig', 'legacy', 'classmethod',
            migration='use the cli classmethod instead.',
            deprecate='0.7.2', error='1.0.0', remove='1.0.1',
        )
        if default is None:
            default = {}
        self = cls(**default)
        self.load(data, cmdline=cmdline, default=default, strict=strict)
        return self

    @classmethod
    def parse_args(cls, args=None, namespace=None):
        """
        Mimics argparse.ArgumentParser.parse_args
        """
        if namespace is not None:
            raise NotImplementedError(
                'namespaces are not handled in scriptconfig')
        return cls.cli(argv=args, strict=True)

    @classmethod
    def parse_known_args(cls, args=None, namespace=None):
        """
        Mimics argparse.ArgumentParser.parse_known_args
        """
        if namespace is not None:
            raise NotImplementedError(
                'namespaces are not handled in scriptconfig')
        return cls.cli(argv=args, strict=False)

    @classmethod
    def _class_has_subconfigs(cls):
        return class_has_subconfigs(cls)

    @classmethod
    def cli(cls, data=None, default=None, argv=None, strict=True,
            cmdline=True, autocomplete='auto', special_options=True,
            transition_helpers=True, verbose=False, allow_import=False):
        """
        Command-line aware constructor with nested SubConfig support.

        Uses a staged parse when SubConfig fields are present. If the config is
        flat (no SubConfig entries) this dispatches to the legacy fast-path to
        avoid any overhead.
        """
        if not cls._class_has_subconfigs():
            return super().cli(data=data, default=default, argv=argv,
                               strict=strict, cmdline=cmdline,
                               autocomplete=autocomplete,
                               special_options=special_options,
                               transition_helpers=transition_helpers,
                               verbose=verbose)

        import sys
        if diagnostics.DEBUG_CONFIG:
            print(f'[scriptconfig.dataconfig.DataConfig] Call {cls.__name__}.cli (nested mode)')

        if transition_helpers and hasattr(data, 'pop'):
            argv = data.pop('cmdline', argv)  # backwards compat helper
        if cmdline and argv is not None:
            cmdline = argv

        self = cls(_dont_call_post_init=True)
        if default:
            self.update_defaults(default)

        # Copy defaults into working tree
        ensure_subconfigs_instantiated(self, _dont_call_post_init=True)

        argv_list, want_help = coerce_argv(cmdline)

        config_fpath = None
        if special_options:
            config_fpath = scan_config_path(argv_list)

        if config_fpath is not None:
            cfg_updates = coerce_data_updates(config_fpath)
            apply_dot_updates(self, cfg_updates, allow_import=allow_import)

        if data is not None:
            cfg_updates = coerce_data_updates(data)
            apply_dot_updates(self, cfg_updates, allow_import=allow_import)

        # Stage 1: extract selectors from argv and realize tree iteratively
        selector_updates, stage2_argv = extract_selector_overrides(self, argv_list, allow_import=allow_import)
        if selector_updates:
            apply_dot_updates(self, selector_updates, allow_import=allow_import)

        # Stage 2: build a parser for realized leaves and parse remaining args
        flat_helper = _FlatConfig.from_tree(self, include_class_options=True)
        parser = flat_helper.argparse(special_options=special_options)

        if autocomplete:
            try:
                import argcomplete as argcomplete_mod
            except ImportError:
                if autocomplete != 'auto':
                    raise
            else:
                argcomplete_mod.autocomplete(parser)

        try:
            if strict:
                ns_obj, extras = parser.parse_known_args(stage2_argv)
                if extras:
                    unknown = ' '.join(extras)
                    raise KeyError(f'Unknown configuration options: {unknown}')
            else:
                ns_obj = parser.parse_known_args(stage2_argv)[0]
            ns = ns_obj.__dict__
        except (ValueError, TypeError, KeyError) as ex:
            from scriptconfig.util import util_exception
            note = ub.codeblock(
                f'''
                Error while attempting to parse arguments in DataConfig.cli

                Context:
                    argv = {stage2_argv!r}
                    special_options = {special_options!r}
                    strict = {strict!r}
                    autocomplete = {autocomplete!r}
                    self = {self!r}
                ''')
            print(note)
            ex = util_exception.add_exception_note(ex, note)
            raise ex

        special_ns = {}
        if special_options:
            special_ns = {k: ns.pop(k, None) for k in ['config', 'dump', 'dumps']}

        explicit = getattr(parser, '_explicitly_given', set())
        explicit_updates = {k: v for k, v in ns.items() if k in explicit}
        if explicit_updates:
            apply_dot_updates(self, explicit_updates, allow_import=allow_import)

        finalize_post_init(self)

        if special_options:
            handle_special_dump(self, special_ns)

        if isinstance(verbose, str) and verbose == 'auto':
            verbose = self.get('verbose', verbose)
            verbose = not self.get('quiet', not verbose)
            verbose = not self.get('silent', not verbose)

        if verbose:
            try:
                import rich
                from rich.markup import escape
            except ImportError:
                print('config = ' + ub.urepr(self, nl=1))
            else:
                rich.print('config = ' + escape(ub.urepr(self, nl=1)))

        if diagnostics.DEBUG_CONFIG:
            print(f'[scriptconfig.dataconfig.DataConfig] Return {cls.__name__}.cli')
        return self

    def load(self, data=None, cmdline=False, mode=None, default=None,
             strict=False, autocomplete=False, _dont_call_post_init=False,
             special_options=True, allow_import=False):
        """
        Override to support nested SubConfig-aware updates.
        """
        if not self._has_subconfigs:
            return super().load(data=data, cmdline=cmdline, mode=mode,
                                default=default, strict=strict,
                                autocomplete=autocomplete,
                                _dont_call_post_init=_dont_call_post_init,
                                special_options=special_options)

        if default:
            self.update_defaults(default)

        pending_updates = None
        if data is not None:
            cfg_updates = _coerce_data_updates(data, mode=mode)
            pending_updates = cfg_updates
            if not cmdline:
                apply_dot_updates(self, cfg_updates, allow_import=allow_import)

        if cmdline:
            argv = cmdline if cmdline is not True else None
            parsed = self.__class__.cli(data=pending_updates, default=None, argv=argv,
                                        strict=strict, cmdline=cmdline,
                                        autocomplete=autocomplete,
                                        special_options=special_options,
                                        verbose=False,
                                        allow_import=allow_import)
            self._data = parsed._data
            self._default = parsed._default
            self._subconfig_meta = parsed._subconfig_meta
            self._has_subconfigs = parsed._has_subconfigs
        if not _dont_call_post_init:
            finalize_post_init(self)
        return self

    def asdict(self):
        return config_to_nested_dict(self, include_class=False)

    def to_dict(self):
        return self.asdict()

    def dump(self, stream=None, mode=None):
        if mode is None:
            mode = 'yaml'
        payload = config_to_nested_dict(self, include_class=True)
        if mode == 'yaml':
            import yaml
            def order_rep(dumper, data):
                return dumper.represent_mapping('tag:yaml.org,2002:map', data.items(), flow_style=False)
            yaml.add_representer(OrderedDict, order_rep, Dumper=yaml.SafeDumper)
            yaml.safe_dump(payload, stream)
        elif mode == 'json':
            import json
            json.dump(payload, stream, indent=4)
        else:
            raise KeyError(mode)

    def dumps(self, mode=None):
        import io
        stream = io.StringIO()
        self.dump(stream=stream, mode=mode)
        return stream.getvalue()

    @property
    def default(self):
        import ubelt as ub
        ub.schedule_deprecation(
            'scriptconfig', 'default', 'attribute',
            migration='use the __default__ instead.',
            deprecate='0.7.7', error='1.0.0', remove='1.0.1',
        )
        return self.__default__

    @classmethod
    def _register_main(cls, func):
        """
        Register a function as the main method for this dataconfig CLI
        """
        cls.main = func
        return func


def __example__():
    """
    Doctests are broken for DataConfigs, so putting them here.
    """
    import scriptconfig as scfg
    try:
        import dataclasses
    except ImportError:
        dataclasses = None

    @dataclasses.dataclass
    class ExampleDataConfig0:
        x: int = 0
        y: str = 3

    ### Different variants of the same basic configuration (varying amounts of metadata)
    class ExampleDataConfig1:
        chip_dims = (256, 256)
        time_dim = 5
        channels = 'red|green|blue'
        time_sampling = 'soft2'

    ExampleDataConfig1d = dataclasses.dataclass(ExampleDataConfig1)

    @dataclasses.dataclass
    class ExampleDataConfig2:
        chip_dims = scfg.Value((256, 256), help='chip size')
        time_dim = scfg.Value(3, help='number of time steps')
        channels = scfg.Value('*:(red|green|blue)', help='sensor / channel code')
        time_sampling = scfg.Value('soft2')

    @dataclasses.dataclass
    class ExampleDataConfig2d:
        chip_dims = scfg.Value((256, 256), help='chip size')
        time_dim: int = scfg.Value(3, help='number of time steps')
        channels: str = scfg.Value('*:(red|green|blue)', help='sensor / channel code')
        time_sampling: str = scfg.Value('soft2')

    class ExampleDataConfig3:
        __default__ = {
            'chip_dims': scfg.Value((256, 256), help='chip size'),
            'time_dim': scfg.Value(3, type=int, help='number of time steps'),
            'channels': scfg.Value('*:(red|green|blue)', type=str, help='sensor / channel code'),
            'time_sampling': scfg.Value('soft2', type=str),
        }

    classes = [ExampleDataConfig0, ExampleDataConfig1, ExampleDataConfig1d,
               ExampleDataConfig2, ExampleDataConfig2d, ExampleDataConfig3]
    for cls in classes:
        dcls = dataconf(cls)
        self = dcls()
        print(f'self={self}')

    # cls = ExampleDataConfig2
    # cls.__annotations__['channels'].__dict__
    # cls.__annotations__['set_cover_algo'].__dict__
    # # @scfg.dataconfig
