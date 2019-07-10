import dataclasses
import datetime
import inspect
import typing
from operator import attrgetter

import pytest

from tests.objects import (
    FromDict,
    Data,
    Nested,
    NestedSeq,
    NestedFromDict,
    DefaultNone,
    Forward,
    FooNum,
    UserID,
    DateDict,
    NoParams,
    Class,
    func,
    Frozen,
    optional,
    varargs,
    Typic,
    FrozenTypic,
    Inherited,
    KlassVar,
    KlassVarSubscripted,
    Method,
    KlassDelayed,
    Delayed,
    delayed,
)
from typic.checks import isbuiltintype, BUILTIN_TYPES, resolve_supertype
from typic.eval import safe_eval
from typic.typed import coerce, typed, resolve


@pytest.mark.parametrize(argnames="obj", argvalues=BUILTIN_TYPES)
def test_isbuiltintype(obj: typing.Any):
    assert isbuiltintype(obj)


@pytest.mark.parametrize(
    argnames=("annotation", "value"),
    argvalues=[
        (dict, [("foo", "bar")]),
        (typing.Dict, [("foo", "bar")]),
        (list, set()),
        (typing.List, set()),
        (set, list()),
        (typing.Set, list()),
        (tuple, list()),
        (typing.Tuple, list()),
        (str, 1),
        (typing.Text, 1),
        (float, 1),
        (bool, 1),
        (datetime.datetime, "1970-01-01"),
        (datetime.datetime, 0),
        (datetime.date, "1970-01-01"),
        (datetime.date, 0),
        (datetime.datetime, datetime.date(1980, 1, 1)),
        (datetime.date, datetime.datetime(1980, 1, 1)),
        (FromDict, {"foo": "bar!"}),
        (Data, {"foo": "bar!"}),
        (Nested, {"data": {"foo": "bar!"}}),
        (NestedFromDict, {"data": {"foo": "bar!"}}),
        (FooNum, "bar"),
        (Data, Data("bar!")),
    ],
)
def test_coerce_simple(annotation, value):
    coerced = coerce(value, annotation)
    assert isinstance(coerced, annotation)


@pytest.mark.parametrize(argnames=("annotation", "value"), argvalues=[(UserID, "1")])
def test_coerce_newtype(annotation, value):
    coerced = coerce(value, annotation)
    assert isinstance(coerced, annotation.__supertype__)


def test_default_none():
    coerced = coerce({}, DefaultNone)
    assert coerced.none is None


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (typing.Optional[str], 1, "1"),
        (typing.Optional[str], None, None),
        (typing.ClassVar[str], 1, "1"),
    ],
)
def test_coerce_supscripted(annotation, value, expected):
    assert coerce(value, annotation) == expected


@pytest.mark.parametrize(
    argnames=("annotation", "value"),
    argvalues=[
        (typing.List[int], '["1"]'),
        (typing.List[bool], '["1"]'),
        (typing.List[int], ("1",)),
        (typing.Set[int], '["1"]'),
        (typing.Set[bool], '["1"]'),
        (typing.Set[int], ("1",)),
        (typing.Tuple[int], '["1"]'),
        (typing.Tuple[bool], '["1"]'),
        (typing.Tuple[int], {"1"}),
        (typing.Sequence[int], '["1"]'),
        (typing.Sequence[bool], '["1"]'),
        (typing.Sequence[int], {"1"}),
        (typing.Collection[int], '["1"]'),
        (typing.Collection[bool], '["1"]'),
        (typing.Collection[int], {"1"}),
        (typing.Collection[FromDict], [{"foo": "bar!"}]),
        (typing.Collection[Data], [{"foo": "bar!"}]),
        (typing.Collection[Nested], [{"data": {"foo": "bar!"}}]),
        (typing.Collection[NestedFromDict], [{"data": {"foo": "bar!"}}]),
        (typing.Collection[NestedFromDict], ["{'data': {'foo': 'bar!'}}"]),
    ],
)
def test_coerce_collections_subscripted(annotation, value):
    arg = annotation.__args__[0]
    coerced = coerce(value, annotation)
    assert isinstance(coerced, annotation.__origin__) and all(
        isinstance(x, arg) for x in coerced
    )


@pytest.mark.parametrize(
    argnames=("annotation", "value"),
    argvalues=[
        (typing.Mapping[int, str], '{"1": 0}'),
        (typing.Mapping[int, bool], '{"1": false}'),
        (typing.Mapping[str, int], {1: "0"}),
        (typing.Mapping[str, bool], {1: "0"}),
        (typing.Mapping[datetime.datetime, datetime.datetime], {0: "1970"}),
        (typing.Dict[int, str], '{"1": 0}'),
        (typing.Dict[str, int], {1: "0"}),
        (typing.Dict[str, bool], {1: "0"}),
        (typing.Dict[datetime.datetime, datetime.datetime], {0: "1970"}),
        (typing.Dict[str, FromDict], {"blah": {"foo": "bar!"}}),
        (typing.Mapping[int, Data], {"0": {"foo": "bar!"}}),
        (typing.Dict[datetime.date, Nested], {"1970": {"data": {"foo": "bar!"}}}),
        (typing.Mapping[bool, NestedFromDict], {0: {"data": {"foo": "bar!"}}}),
        (typing.Dict[bytes, NestedFromDict], {0: "{'data': {'foo': 'bar!'}}"}),
        (DateDict, '{"1970": "foo"}'),
    ],
)
def test_coerce_mapping_subscripted(annotation, value):
    annotation = resolve_supertype(annotation)
    key_arg, value_arg = annotation.__args__
    coerced = coerce(value, annotation)
    assert isinstance(coerced, annotation.__origin__)
    assert all(isinstance(x, key_arg) for x in coerced.keys())
    assert all(isinstance(x, value_arg) for x in coerced.values())


def test_coerce_nested_sequence():
    coerced = coerce({"datum": [{"foo": "bar"}]}, NestedSeq)
    assert isinstance(coerced, NestedSeq)
    assert all(isinstance(x, Data) for x in coerced.datum)


@pytest.mark.parametrize(
    argnames=("func", "input", "type"),
    argvalues=[(func, "1", int), (Method().math, "4", int)],
)
def test_wrap_callable(func, input, type):
    wrapped = coerce.wrap(func)
    assert isinstance(wrapped(input), type)


@pytest.mark.parametrize(
    argnames=("klass", "var", "type"),
    argvalues=[(Class, "var", str), (Data, "foo", str)],
)
def test_wrap_class(klass, var, type):
    Wrapped = coerce.wrap_cls(klass)
    assert isinstance(getattr(Wrapped(1), var), type)
    assert inspect.isclass(Wrapped)


@pytest.mark.parametrize(
    argnames=("obj", "input", "getter", "type", "check"),
    argvalues=[
        (func, "1", None, int, inspect.isfunction),
        (optional, 1, None, str, inspect.isfunction),
        (optional, None, None, type(None), inspect.isfunction),
        (Data, 1, attrgetter("foo"), str, inspect.isclass),
        (DefaultNone, None, attrgetter("none"), type(None), inspect.isclass),
        (Forward, "bar", attrgetter("foo"), FooNum, inspect.isclass),
        (Frozen, "0", attrgetter("var"), bool, inspect.isclass),
    ],
)
def test_typed(obj, input, getter, type, check):
    wrapped = typed(obj)
    result = wrapped(input)
    if getter:
        result = getter(result)
    assert check(wrapped)
    assert isinstance(result, type)


def test_ensure_invalid():
    with pytest.raises(TypeError):
        typed(1)


@pytest.mark.parametrize(
    argnames=("func", "args", "kwargs", "check"),
    argvalues=[
        (
            varargs,
            ({"foo": "bar"},),
            {"bar": {"foo": "bar"}},
            lambda res: all(isinstance(x, Data) for x in res),
        )
    ],
)
def test_typed_varargs(func, args, kwargs, check):
    wrapped = typed(func)
    result = wrapped(*args, **kwargs)

    assert check(result)


@pytest.mark.parametrize(
    argnames=("annotation", "origin"),
    argvalues=[
        (typing.Mapping[int, str], dict),
        (typing.Mapping, dict),
        (DateDict, dict),
        (UserID, int),
    ],
)
def test_get_origin_returns_origin(annotation, origin):
    detected = coerce.get_origin(annotation)
    assert detected is origin


def test_eval_invalid():
    processed, result = safe_eval("{")
    assert not processed
    assert result == "{"


@pytest.mark.parametrize(
    argnames=("annotation",), argvalues=[(typing.Any,), (typing.Union,)]
)
def test_special_form(annotation):
    param = inspect.Parameter(
        "foo", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation
    )
    assert coerce.should_coerce(param, "foo") is False


@pytest.mark.parametrize(
    argnames=("instance", "attr", "value", "type"),
    argvalues=[(typed(Data)("foo"), "foo", 1, str), (typed(NoParams)(), "var", 1, str)],
)
def test_setattr(instance, attr, value, type):
    setattr(instance, attr, value)
    assert isinstance(getattr(instance, attr), type)


def test_register():
    class MyCustomClass:
        def __init__(self, value: str):
            self.value = value

    class MyOtherCustomClass:
        def __init__(self, value: int):
            self.value = value

    MyCustomType = typing.Union[MyCustomClass, MyOtherCustomClass]

    def ismycustomclass(obj) -> bool:
        args = set(getattr(obj, "__args__", [obj]))
        return set(MyCustomType.__args__).issuperset(args)

    coerce.register(MyCustomClass, ismycustomclass, check_origin=False)
    assert coerce.registry.check(MyCustomType, MyCustomType)


def test_no_coercer():
    assert isinstance(coerce("foo", lambda x: 1), str)


def test_typic_klass():
    assert Typic(1).var == "1"


def test_typic_klass_is_dataclass():
    assert dataclasses.is_dataclass(Typic)


def test_typic_klass_passes_params():
    with pytest.raises(dataclasses.FrozenInstanceError):
        FrozenTypic(1).var = 2


def test_typic_klass_inheritance():
    assert isinstance(Inherited(1).var, str)


def test_typic_frozen():
    assert isinstance(FrozenTypic(1).var, str)


@pytest.mark.parametrize(
    argnames=("instance", "attr", "type"),
    argvalues=[(KlassVar(), "var", int), (KlassVarSubscripted(), "var", str)],
)
def test_classvar(instance, attr, type):
    setattr(instance, attr, 1)
    assert isinstance(getattr(instance, attr), type)


def test_typic_klass_delayed():
    assert not hasattr(KlassDelayed, "__typic_annotations__")
    assert isinstance(KlassDelayed(1).foo, str)
    assert hasattr(KlassDelayed, "__typic_annotations__")


def test_typic_class_delayed():
    assert not hasattr(Delayed, "__typic_annotations__")
    assert isinstance(Delayed(1).foo, str)
    assert hasattr(Delayed, "__typic_annotations__")
    del Delayed.__typic_annotations__


def test_typic_callable_delayed():
    assert isinstance(delayed(1), str)


def test_typic_resolve():
    assert not hasattr(Delayed, "__typic_annotations__")
    resolve()
    assert hasattr(Delayed, "__typic_annotations__")
