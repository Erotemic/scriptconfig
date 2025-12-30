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
from collections.abc import Mapping
from scriptconfig.config import Config, MetaConfig
from scriptconfig.value import Value
import inspect
import warnings
import ubelt as ub
from scriptconfig import diagnostics


__all__ = ['dataconf', 'DataConfig', 'MetaDataConfig', 'SubConfig']


class SubConfig(ub.NiceRepr):
    """
    Wrapper used to declare nested :class:`DataConfig` nodes.

    Attributes:
        default (Type[DataConfig] | DataConfig):
            Either a DataConfig subclass or instance used as the default
            nested node.

        choices (dict | None):
            Optional registry mapping of selector keys to DataConfig
            subclasses.

        allow_import (bool):
            If True, allow dotted-path class specs (``module:Class``) to
            dynamically import DataConfig subclasses when selected via CLI or
            programmatic overrides.
    """

    __scfg_class__ = 'SubConfig'

    def __init__(self, default, *, choices=None, allow_import=None):
        if inspect.isclass(default):
            if not issubclass(default, Config):
                raise TypeError('SubConfig default must be a Config / DataConfig subclass')
            self.default = default
        elif isinstance(default, Config):
            self.default = default
        else:
            raise TypeError('SubConfig default must be a Config / DataConfig instance or class')

        if choices is not None:
            self.choices = dict(choices)
            for key, cls in self.choices.items():
                if not inspect.isclass(cls) or not issubclass(cls, Config):
                    raise TypeError(f'SubConfig choices must map to Config subclasses. {key!r} -> {cls!r}')
        else:
            self.choices = None
        self.allow_import = allow_import

    def __nice__(self):
        default_cls = self.default if inspect.isclass(self.default) else self.default.__class__
        return f'{default_cls.__name__}'

    def instantiate(self, *, _dont_call_post_init=False):
        """Return a fresh instance of the wrapped config."""
        import copy
        if inspect.isclass(self.default):
            instance = self.default(_dont_call_post_init=_dont_call_post_init)
        else:
            instance = copy.deepcopy(self.default)
            if _dont_call_post_init and hasattr(instance, '_enable_setattr'):
                instance._enable_setattr = True
        return instance


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

        for k, v in self._default.items():
            if isinstance(v, SubConfig):
                self._has_subconfigs = True
                self._subconfig_meta[k] = v
                self._data[k] = v.instantiate(_dont_call_post_init=_dont_call_post_init)

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
        default = getattr(cls, '__default__', None) or {}
        return any(isinstance(v, SubConfig) for v in default.values())

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
        _ensure_subconfigs_instantiated(self, _dont_call_post_init=True)

        argv_list, want_help = _coerce_argv(cmdline)

        config_fpath = None
        if special_options:
            config_fpath = _scan_config_path(argv_list)

        if config_fpath is not None:
            cfg_updates = _coerce_data_updates(config_fpath)
            apply_dot_updates(self, cfg_updates, allow_import=allow_import)

        if data is not None:
            cfg_updates = _coerce_data_updates(data)
            apply_dot_updates(self, cfg_updates, allow_import=allow_import)

        # Stage 1: extract selectors from argv and realize tree iteratively
        selector_updates, stage2_argv = _extract_selector_overrides(self, argv_list, allow_import=allow_import)
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

        _finalize_post_init(self)

        if special_options:
            _handle_special_dump(self, special_ns)

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
            _finalize_post_init(self)
        return self

    def asdict(self):
        return _config_to_nested_dict(self, include_class=False)

    def to_dict(self):
        return self.asdict()

    def dump(self, stream=None, mode=None):
        if mode is None:
            mode = 'yaml'
        payload = _config_to_nested_dict(self, include_class=True)
        if mode == 'yaml':
            import yaml
            def order_rep(dumper, data):
                return dumper.represent_mapping('tag:yaml.org,2002:map', data.items(), flow_style=False)
            yaml.add_representer(OrderedDict, order_rep)
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


# --- Helper utilities for nested DataConfigs ---


def _ensure_subconfigs_instantiated(cfg, _dont_call_post_init=False):
    if not getattr(cfg, '_has_subconfigs', False):
        return
    for key, meta in getattr(cfg, '_subconfig_meta', {}).items():
        if not isinstance(cfg._data.get(key), Config):
            cfg._data[key] = meta.instantiate(_dont_call_post_init=_dont_call_post_init)


def _coerce_argv(cmdline):
    import shlex
    import sys
    if not cmdline:
        return [], False
    if cmdline is True:
        argv = sys.argv[1:]
    elif isinstance(cmdline, str):
        argv = shlex.split(cmdline)
    elif ub.iterable(cmdline):
        argv = list(cmdline)
    else:
        raise TypeError(f'Unsupported argv={cmdline!r}')
    want_help = any(a in {'-h', '--help'} for a in argv)
    return argv, want_help


def _scan_config_path(argv):
    config_fpath = None
    for i, tok in enumerate(argv):
        if tok == '--config':
            if i + 1 >= len(argv):
                raise ValueError('--config requires a value')
            config_fpath = argv[i + 1]
        elif tok.startswith('--config='):
            config_fpath = tok.split('=', 1)[1]
    return config_fpath


def _coerce_data_updates(data, mode=None):
    """
    Convert a data source (dict or filepath) into dotted updates.
    """
    if data is None:
        return {}

    import os
    from scriptconfig.file_like import FileLike

    if isinstance(data, (str, os.PathLike)) or hasattr(data, 'readable'):
        if isinstance(data, str) and ('\n' in data or not os.path.exists(data)):
            import json
            try:
                user_config = json.loads(data)
            except Exception:
                import yaml
                import io
                file = io.StringIO(data)
                user_config = yaml.load(file, Loader=yaml.SafeLoader)
        else:
            if mode is None and isinstance(data, (str, os.PathLike)):
                if str(data).lower().endswith('.json'):
                    mode = 'json'
            if mode is None:
                mode = 'yaml'
            with FileLike(data, 'r') as file:
                if mode == 'yaml':
                    import yaml
                    user_config = yaml.load(file, Loader=yaml.SafeLoader)
                elif mode == 'json':
                    import json
                    user_config = json.load(file)
                else:
                    raise KeyError(mode)
    elif isinstance(data, dict):
        user_config = data
    elif isinstance(data, Config):
        user_config = data.to_dict()
    else:
        raise TypeError(f'Expected path or dict, but got {type(data)}')

    flat = OrderedDict()
    for k, v in _flatten_nested(user_config):
        flat[k] = v
    return flat


def _flatten_nested(mapping, prefix=()):
    if isinstance(mapping, Mapping):
        for k, v in mapping.items():
            key = '.'.join(prefix + (k,))
            if isinstance(v, Mapping):
                yield from _flatten_nested(v, prefix + (k,))
            else:
                yield key, v
    else:
        raise TypeError('Expected mapping')


def _split_option_token(argv, idx):
    tok = argv[idx]
    if not tok.startswith('--'):
        return None, None, 1
    key = tok[2:]
    if '=' in key:
        key, val = key.split('=', 1)
        return key, val, 1
    if idx + 1 < len(argv):
        nxt = argv[idx + 1]
        if not nxt.startswith('-') or nxt == '-':
            return key, nxt, 2
    return key, None, 1


def _path_is_subconfig(cfg, parts):
    node = cfg
    for idx, part in enumerate(parts):
        if part == '__class__':
            return False
        if not isinstance(node, DataConfig):
            return False
        if part in getattr(node, '_subconfig_meta', {}):
            if idx == len(parts) - 1:
                return True
            child = node._data.get(part)
            if isinstance(child, Config):
                node = child
            else:
                return False
        elif part in node._data and isinstance(node._data[part], Config):
            node = node._data[part]
        else:
            return False
    return False


def _extract_selector_overrides(cfg, argv, allow_import=False):
    """
    Extract and apply selector-like arguments from argv in a staged manner.
    """
    working = list(argv)
    collected = {}
    changed = True
    max_iter = 20
    guard = 0
    while changed:
        guard += 1
        if guard > max_iter:
            raise RuntimeError('Selector resolution did not converge')
        changed = False
        new_selectors = {}
        kept = []
        i = 0
        while i < len(working):
            tok = working[i]
            key, val, consumed = _split_option_token(working, i)
            if key is None:
                kept.append(tok)
                i += 1
                continue
            if key.endswith('.__class__'):
                sel_key = key[:-len('.__class__')]
                if val is None:
                    raise ValueError(f'Missing value for selector {key}')
                new_selectors[sel_key] = val
                changed = True
                i += consumed
                continue
            if _path_is_subconfig(cfg, key.split('.')):
                if val is None:
                    raise ValueError(f'Missing value for selector {key}')
                new_selectors[key] = val
                changed = True
                i += consumed
                continue
            kept.append(tok)
            i += 1
        if new_selectors:
            collected.update(new_selectors)
            working = kept
            apply_dot_updates(cfg, new_selectors, allow_import=allow_import)
        else:
            working = kept
    return collected, working


def _ensure_parent_node(cfg, parts):
    node = cfg
    for part in parts:
        if not isinstance(node, DataConfig):
            raise KeyError('.'.join(parts))
        if part in getattr(node, '_subconfig_meta', {}):
            child = node._data.get(part)
            if not isinstance(child, Config):
                child = node._subconfig_meta[part].instantiate(_dont_call_post_init=True)
                node._data[part] = child
            node = child
        elif part in node._data and isinstance(node._data[part], Config):
            node = node._data[part]
        else:
            raise KeyError('.'.join(parts))
    return node


def _resolve_class_spec(meta, spec, allow_import):
    if meta.choices and spec in meta.choices:
        return meta.choices[spec]
    if inspect.isclass(spec) and issubclass(spec, Config):
        return spec
    if isinstance(spec, str):
        if not (meta.allow_import or allow_import):
            raise ValueError(f'Importing {spec!r} not allowed for this SubConfig')
        if ':' in spec:
            modname, clsname = spec.split(':', 1)
        else:
            # fallback simple form
            parts = spec.rsplit('.', 1)
            if len(parts) != 2:
                raise ValueError(f'Cannot interpret class spec {spec!r}')
            modname, clsname = parts
        import importlib
        mod = importlib.import_module(modname)
        if not hasattr(mod, clsname):
            raise ValueError(f'Module {modname!r} has no attribute {clsname!r}')
        cls = getattr(mod, clsname)
        if not inspect.isclass(cls) or not issubclass(cls, Config):
            raise TypeError(f'Specified class {cls!r} is not a Config/DataConfig')
        return cls
    raise ValueError(f'Unknown selector spec {spec!r}')


def _apply_selectors_fixpoint(cfg, selectors, allow_import=False):
    remaining = dict(selectors)
    applied_any = True
    max_iter = 32
    iter_idx = 0
    while applied_any:
        iter_idx += 1
        if iter_idx > max_iter:
            raise RuntimeError('Selector resolution failed to converge')
        applied_any = False
        for path, spec in list(remaining.items()):
            parts = tuple(p for p in path.split('.') if p)
            if not parts:
                raise ValueError('Empty selector path')
            parent_parts, leaf = parts[:-1], parts[-1]
            try:
                parent = _ensure_parent_node(cfg, parent_parts)
            except KeyError:
                continue
            if not isinstance(parent, DataConfig):
                continue
            meta = getattr(parent, '_subconfig_meta', {}).get(leaf, None)
            if meta is None:
                continue
            cls = _resolve_class_spec(meta, spec, allow_import)
            parent._data[leaf] = cls(_dont_call_post_init=True)
            applied_any = True
            remaining.pop(path, None)
    if remaining:
        raise KeyError(f'Could not resolve selectors for: {sorted(remaining)}')


def apply_dot_updates(cfg, updates, *, allow_import=False):
    """
    Apply dotted-path updates and selectors to a nested DataConfig.
    """
    if not updates:
        return cfg

    flat_updates = OrderedDict()
    if isinstance(updates, dict):
        for k, v in _flatten_nested(updates):
            flat_updates[k] = v
    else:
        raise TypeError('updates must be a mapping')

    selectors = {}
    leaf_updates = {}
    for key, value in flat_updates.items():
        if key.endswith('.__class__'):
            selectors[key[:-len('.__class__')]] = value
        else:
            leaf_updates[key] = value

    _apply_selectors_fixpoint(cfg, selectors, allow_import=allow_import)

    # Reclassify sugar selectors now that selectors may have been applied.
    sugar = {}
    for key, value in list(leaf_updates.items()):
        parts = key.split('.')
        try:
            parent = _ensure_parent_node(cfg, parts[:-1])
        except KeyError:
            continue
        if isinstance(parent, DataConfig) and parts[-1] in getattr(parent, '_subconfig_meta', {}):
            if key not in selectors:
                sugar[key] = value
                leaf_updates.pop(key, None)
    if sugar:
        _apply_selectors_fixpoint(cfg, sugar, allow_import=allow_import)

    for key, value in leaf_updates.items():
        parts = key.split('.')
        parent = _ensure_parent_node(cfg, parts[:-1])
        leaf = parts[-1]
        if leaf == '__class__':
            raise KeyError('The name "__class__" is reserved for selector metadata')
        if leaf not in parent._data:
            leaf = parent._normalize_alias_key(leaf)
        if leaf not in parent._data:
            raise KeyError(f'Unknown configuration key: {key}')
        parent[leaf] = value
    return cfg


def _flatten_defaults(cfg, prefix=(), include_class_options=False):
    flat = OrderedDict()
    for key, value in cfg._data.items():
        if key in getattr(cfg, '_subconfig_meta', {}):
            if include_class_options:
                class_key = '.'.join(prefix + (key, '__class__'))
                flat[class_key] = Value(None, help=f'{key} implementation selector')
            if isinstance(value, Config):
                flat.update(_flatten_defaults(value, prefix + (key,), include_class_options))
        elif isinstance(value, Config):
            flat.update(_flatten_defaults(value, prefix + (key,), include_class_options))
        else:
            meta = cfg._default.get(key)
            leaf_key = '.'.join(prefix + (key,))
            if isinstance(meta, Value):
                flat[leaf_key] = meta
            else:
                flat[leaf_key] = value
    return flat


class _FlatConfig(Config):
    """
    Helper Config used to parse realized leaf arguments via argparse.
    """
    __default__ = {}

    @classmethod
    def from_tree(cls, cfg, include_class_options=False):
        defaults = _flatten_defaults(cfg, include_class_options=include_class_options)
        name = f'_Flat_{cfg.__class__.__name__}'
        FlatCls = type(name, (Config,), {'__default__': defaults})
        return FlatCls(_dont_call_post_init=True)


def _finalize_post_init(cfg):
    if isinstance(cfg, DataConfig):
        if not getattr(cfg, '_scfg_post_init_done', False):
            cfg.__post_init__()
            cfg._scfg_post_init_done = True
    if isinstance(cfg, Config):
        for value in cfg._data.values():
            if isinstance(value, Config):
                _finalize_post_init(value)


def _handle_special_dump(cfg, special_ns):
    import sys
    dump_fpath = special_ns.get('dump')
    do_dumps = special_ns.get('dumps')
    if dump_fpath or do_dumps:
        if dump_fpath:
            if dump_fpath.lower().endswith('.json'):
                mode = 'json'
            elif dump_fpath.lower().endswith('.yaml'):
                mode = 'yaml'
            else:
                mode = 'yaml'
            text = cfg.dumps(mode=mode)
            with open(dump_fpath, 'w') as file:
                file.write(text)
        if do_dumps:
            text = cfg.dumps(mode='yaml')
            print(text)
        sys.exit(1)


def _class_identifier(cls):
    return f'{cls.__module__}:{cls.__name__}'


def _config_to_nested_dict(cfg, include_class=False):
    def unwrap(val):
        if isinstance(val, Value):
            return val.value
        return val

    result = OrderedDict()
    for key, value in cfg._data.items():
        if isinstance(value, Config):
            child = _config_to_nested_dict(value, include_class=include_class)
            if include_class:
                child['__class__'] = _class_identifier(value.__class__)
            result[key] = child
        else:
            result[key] = unwrap(value)
    return result
