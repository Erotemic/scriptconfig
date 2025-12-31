"""
Helpers for nested configuration nodes built from Config / DataConfig objects.

The :class:`SubConfig` wrapper marks a nested :class:`Config` (or subclass)
and optionally exposes a registry of valid choices or a permissive import
mechanism for dynamically specified class paths.

The rest of this module contains utilities that both :class:`Config` and
:class:`DataConfig` can use to realize nested configuration trees from
defaults, files, kwargs, and staged CLI parsing.

Example:
    >>> import scriptconfig as scfg
    >>> class Inner(scfg.DataConfig):
    ...     depth = 1
    >>> class Outer(scfg.DataConfig):
    ...     inner = scfg.SubConfig(Inner, choices={'inner': Inner})
    >>> cfg = Outer.cli(argv=['--inner.depth=3'])
    >>> assert cfg.inner.depth == 3
    >>> cfg2 = Outer.cli(argv=['--inner=inner', '--inner.depth=4'])
    >>> assert isinstance(cfg2.inner, Inner) and cfg2.inner.depth == 4
"""
from __future__ import annotations

import inspect
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any, Dict, Iterable, Tuple

import ubelt as ub

from scriptconfig.config import Config
from scriptconfig.value import Value

__all__ = [
    'SubConfig',
    'apply_dot_updates',
    'class_has_subconfigs',
    'config_to_nested_dict',
    'coerce_argv',
    'coerce_data_updates',
    'ensure_subconfigs_instantiated',
    'extract_selector_overrides',
    'finalize_post_init',
    'flatten_defaults',
    'handle_special_dump',
    'scan_config_path',
    'wrap_subconfig_defaults',
]


class SubConfig(Value):
    """
    Wrapper used to declare nested :class:`Config` / :class:`DataConfig` nodes.

    Args:
        default (Type[Config] | Config): a Config subclass or instance.
        choices (dict | None): optional registry mapping selector keys to
            Config subclasses.
        allow_import (bool): if True, allow class-path selectors
            (``module:Class``) to be dynamically imported.
    """

    __scfg_class__ = 'SubConfig'

    def __init__(self, default, *, choices=None, allow_import=None, help=None):
        if inspect.isclass(default):
            if not issubclass(default, Config):
                raise TypeError('SubConfig default must be a Config subclass or instance')
            default_inst = default
        elif isinstance(default, Config):
            default_inst = default
        else:
            raise TypeError('SubConfig default must be a Config subclass or instance')

        super().__init__(value=default_inst, help=help)
        self.allow_import = allow_import
        self.choices = dict(choices) if choices is not None else None
        if self.choices is not None:
            for key, cls in self.choices.items():
                if not inspect.isclass(cls) or not issubclass(cls, Config):
                    raise TypeError(f'SubConfig choices must map to Config subclasses. {key!r} -> {cls!r}')

    def __nice__(self):
        default_cls = self.value if inspect.isclass(self.value) else self.value.__class__
        return f'{default_cls.__name__}'

    def instantiate(self, *, _dont_call_post_init=False):
        """
        Return a fresh instance of the wrapped config.
        """
        import copy
        if inspect.isclass(self.value):
            instance = self.value(_dont_call_post_init=_dont_call_post_init)
        else:
            instance = copy.deepcopy(self.value)
            if _dont_call_post_init and hasattr(instance, '_enable_setattr'):
                instance._enable_setattr = True
        return instance


def class_has_subconfigs(cls):
    default = getattr(cls, '__default__', None) or {}
    return any(isinstance(v, SubConfig) or isinstance(v, Config) for v in default.values())


def wrap_subconfig_defaults(cfg, _dont_call_post_init=False):
    """
    Normalize any SubConfig / Config defaults into tracked metadata.
    """
    cfg._subconfig_meta = {}
    cfg._has_subconfigs = False
    for k, v in list(cfg._default.items()):
        meta = None
        if isinstance(v, SubConfig):
            meta = v
        elif isinstance(v, Config):
            meta = SubConfig(v)
            cfg._default[k] = meta
        elif inspect.isclass(v) and issubclass(v, Config):
            meta = SubConfig(v)
            cfg._default[k] = meta
        if meta is not None:
            cfg._has_subconfigs = True
            cfg._subconfig_meta[k] = meta
            cfg._data[k] = meta.instantiate(_dont_call_post_init=_dont_call_post_init)


def ensure_subconfigs_instantiated(cfg, _dont_call_post_init=False):
    if not getattr(cfg, '_has_subconfigs', False):
        return
    for key, meta in getattr(cfg, '_subconfig_meta', {}).items():
        if not isinstance(cfg._data.get(key), Config):
            cfg._data[key] = meta.instantiate(_dont_call_post_init=_dont_call_post_init)


def coerce_argv(cmdline):
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


def scan_config_path(argv):
    config_fpath = None
    for i, tok in enumerate(argv):
        if tok == '--config':
            if i + 1 >= len(argv):
                raise ValueError('--config requires a value')
            config_fpath = argv[i + 1]
        elif tok.startswith('--config='):
            config_fpath = tok.split('=', 1)[1]
    return config_fpath


def coerce_data_updates(data, mode=None):
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
    elif isinstance(data, Mapping):
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
        if not isinstance(node, Config):
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


def extract_selector_overrides(cfg, argv, allow_import=False):
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
        if not isinstance(node, Config):
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


def _resolve_class_spec(meta: SubConfig, spec, allow_import):
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
            if not isinstance(parent, Config):
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
    Apply dotted-path updates and selectors to a nested Config / DataConfig.
    """
    if not updates:
        return cfg

    flat_updates = OrderedDict()
    if isinstance(updates, Mapping):
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

    sugar = {}
    for key, value in list(leaf_updates.items()):
        parts = key.split('.')
        try:
            parent = _ensure_parent_node(cfg, parts[:-1])
        except KeyError:
            continue
        if isinstance(parent, Config) and parts[-1] in getattr(parent, '_subconfig_meta', {}):
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


def flatten_defaults(cfg, prefix=(), include_class_options=False):
    flat = OrderedDict()
    for key, value in cfg._data.items():
        if key in getattr(cfg, '_subconfig_meta', {}):
            if include_class_options:
                class_key = '.'.join(prefix + (key, '__class__'))
                flat[class_key] = Value(None, help=f'{key} implementation selector')
            if isinstance(value, Config):
                flat.update(flatten_defaults(value, prefix + (key,), include_class_options))
        elif isinstance(value, Config):
            flat.update(flatten_defaults(value, prefix + (key,), include_class_options))
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
        defaults = flatten_defaults(cfg, include_class_options=include_class_options)
        name = f'_Flat_{cfg.__class__.__name__}'
        FlatCls = type(name, (Config,), {'__default__': defaults})
        return FlatCls(_dont_call_post_init=True)


def finalize_post_init(cfg):
    if isinstance(cfg, Config):
        if not getattr(cfg, '_scfg_post_init_done', False):
            cfg.__post_init__()
            cfg._scfg_post_init_done = True
    if isinstance(cfg, Config):
        for value in cfg._data.values():
            if isinstance(value, Config):
                finalize_post_init(value)


def handle_special_dump(cfg, special_ns):
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


def config_to_nested_dict(cfg, include_class=False):
    def unwrap(val):
        if isinstance(val, Value):
            return val.value
        return val

    result = OrderedDict()
    meta_map = getattr(cfg, '_subconfig_meta', {})
    for key, value in cfg._data.items():
        meta = meta_map.get(key)
        if isinstance(value, Config):
            child = config_to_nested_dict(value, include_class=include_class)
            if include_class:
                selector = None
                if meta is not None and meta.choices:
                    for name, cls in meta.choices.items():
                        if isinstance(value, cls):
                            selector = name
                            break
                if selector is None:
                    selector = _class_identifier(value.__class__)
                child['__class__'] = selector
            result[key] = child
        else:
            result[key] = unwrap(value)
    return result
