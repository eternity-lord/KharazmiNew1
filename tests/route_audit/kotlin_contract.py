"""Gson/Kotlin contract parser used by the route audit.

The parser reads Android ``data class`` primary-constructor fields directly from
source (including nullability and ``@SerializedName``).  Deserialization is
modelled against the project's actual Retrofit configuration: the app calls
``GsonConverterFactory.create()`` without a custom Gson instance or adapters.
This deliberately does not compile Android.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ANDROID_SRC = ROOT / "KharazmiAdmin/app/src/main/java"
RETROFIT_CLIENT = ANDROID_SRC / "com/example/kharazmiadmin/RetrofitClient.kt"


@dataclass(frozen=True)
class KotlinField:
    name: str
    json_name: str
    type_name: str
    nullable: bool
    line: int
    source: str = ""
    has_default: bool = False
    default_expression: str = ""


@dataclass
class ContractIssue:
    field: str
    kind: str
    detail: str
    line: int
    source: str = ""


@dataclass
class ContractResult:
    model: str
    values: dict[str, Any]
    issues: list[ContractIssue]


def _skip_string_or_comment(text: str, index: int) -> int | None:
    """Return the first index after a string/comment starting at ``index``."""
    if text.startswith("//", index):
        newline = text.find("\n", index + 2)
        return len(text) if newline < 0 else newline + 1
    if text.startswith("/*", index):
        end = text.find("*/", index + 2)
        return len(text) if end < 0 else end + 2
    if text.startswith('"""', index):
        end = text.find('"""', index + 3)
        return len(text) if end < 0 else end + 3
    if text[index] in ('"', "'"):
        quote = text[index]
        cursor = index + 1
        while cursor < len(text):
            if text[cursor] == "\\":
                cursor += 2
                continue
            if text[cursor] == quote:
                return cursor + 1
            cursor += 1
        return len(text)
    return None


def _matching_paren(text: str, opening: int) -> int:
    depth = 1
    cursor = opening + 1
    while cursor < len(text):
        skipped = _skip_string_or_comment(text, cursor)
        if skipped is not None:
            cursor = skipped
            continue
        char = text[cursor]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return len(text)


def _split_top_level(text: str, delimiter: str = ",") -> list[tuple[str, int]]:
    """Split Kotlin constructor parameters without splitting generic arguments."""
    pieces: list[tuple[str, int]] = []
    start = 0
    parens = angles = brackets = braces = 0
    cursor = 0
    while cursor < len(text):
        skipped = _skip_string_or_comment(text, cursor)
        if skipped is not None:
            cursor = skipped
            continue
        char = text[cursor]
        if char == "(": parens += 1
        elif char == ")": parens = max(0, parens - 1)
        elif char == "<": angles += 1
        elif char == ">": angles = max(0, angles - 1)
        elif char == "[": brackets += 1
        elif char == "]": brackets = max(0, brackets - 1)
        elif char == "{": braces += 1
        elif char == "}": braces = max(0, braces - 1)
        elif char == delimiter and not (parens or angles or brackets or braces):
            pieces.append((text[start:cursor], start))
            start = cursor + 1
        cursor += 1
    pieces.append((text[start:], start))
    return pieces


def _before_default(value: str) -> str:
    pieces = _split_top_level(value, delimiter="=")
    return pieces[0][0] if len(pieces) > 1 else value


def _parse_parameter(segment: str, line: int, source: str) -> KotlinField | None:
    field_match = re.search(r"\b(?:val|var)\s+([A-Za-z_$][\w$]*)\s*:\s*", segment)
    if not field_match:
        return None
    name = field_match.group(1)
    type_and_default = segment[field_match.end():]
    default_parts = _split_top_level(type_and_default, delimiter="=")
    has_default = len(default_parts) > 1
    default_expression = re.sub(r"\s+", " ", default_parts[1][0].strip()) if has_default else ""
    type_text = default_parts[0][0].strip()
    # Constructor parameter annotations/modifiers are allowed before `val`; a
    # type may span lines, so normalize only surrounding whitespace here.
    type_text = re.sub(r"\s+", " ", type_text).strip()
    nullable = type_text.endswith("?")
    base_type = type_text[:-1].rstrip() if nullable else type_text
    serialized = re.search(
        r"@SerializedName\s*\(\s*['\"]((?:\\.|[^'\"\\])*)['\"]",
        segment[:field_match.start()],
    )
    json_name = serialized.group(1) if serialized else name
    json_name = json_name.replace(r"\"", '"').replace(r"\'", "'")
    return KotlinField(name, json_name, base_type, nullable, line, source, has_default, default_expression)


def discover_models(root: Path = ANDROID_SRC) -> dict[str, list[KotlinField]]:
    """Find Kotlin data-class constructor contracts, preserving source aliases."""
    found: dict[str, list[KotlinField]] = {}
    class_re = re.compile(r"\bdata\s+class\s+([A-Za-z_$][\w$]*)\s*(?:<[^>]+>\s*)?\(")
    for path in sorted(root.rglob("*.kt")):
        text = path.read_text(encoding="utf-8")
        source = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        for match in class_re.finditer(text):
            opening = text.find("(", match.start())
            closing = _matching_paren(text, opening)
            constructor = text[opening + 1:closing]
            fields: list[KotlinField] = []
            for parameter, relative_offset in _split_top_level(constructor):
                field_line = text[:opening + 1 + relative_offset].count("\n") + 1
                parsed = _parse_parameter(parameter, field_line, source)
                if parsed:
                    fields.append(parsed)
            if fields:
                found[match.group(1)] = fields
    return found


def inspect_gson_configuration(client_file: Path = RETROFIT_CLIENT) -> dict[str, Any]:
    """Report whether Retrofit uses Gson defaults or a project-specific adapter."""
    text = client_file.read_text(encoding="utf-8") if client_file.exists() else ""
    uses_gson_converter = bool(re.search(r"GsonConverterFactory\s*\.\s*create\s*\(\s*\)", text))
    custom_builder = bool(re.search(r"GsonBuilder\s*\(|GsonConverterFactory\s*\.\s*create\s*\(\s*\w", text))
    custom_adapter = bool(re.search(r"registerTypeAdapter|registerTypeHierarchyAdapter|JsonDeserializer|@JsonAdapter", text))
    return {
        "source": str(client_file.relative_to(ROOT)) if client_file.is_relative_to(ROOT) else str(client_file),
        "uses_gson_converter": uses_gson_converter,
        "custom_builder": custom_builder,
        "custom_adapter": custom_adapter,
        "default_gson_semantics": uses_gson_converter and not custom_builder and not custom_adapter,
    }


def _primitive_default(type_name: str) -> Any:
    if type_name in ("Int", "Long", "Short", "Byte"): return 0
    if type_name in ("Float", "Double"): return 0.0
    if type_name == "Boolean": return False
    return None


_UNMODELED_DEFAULT = object()


def _without_comments(text: str) -> str:
    """Remove Kotlin comments without treating comment markers in strings as comments."""
    pieces: list[str] = []
    cursor = 0
    while cursor < len(text):
        if text.startswith("//", cursor):
            newline = text.find("\n", cursor + 2)
            if newline < 0:
                break
            pieces.append(" ")
            cursor = newline + 1
            continue
        if text.startswith("/*", cursor):
            end = text.find("*/", cursor + 2)
            if end < 0:
                break
            pieces.append(" ")
            cursor = end + 2
            continue
        skipped = _skip_string_or_comment(text, cursor)
        if skipped is not None:
            pieces.append(text[cursor:skipped])
            cursor = skipped
            continue
        pieces.append(text[cursor])
        cursor += 1
    return "".join(pieces).strip()


def _kotlin_default(
    expression: str,
    models: dict[str, list[KotlinField]] | None = None,
    _seen: frozenset[str] = frozenset(),
) -> Any:
    """Evaluate common literal/container defaults used by wire DTOs.

    Unsupported expressions are surfaced as simulator gaps rather than guessed.
    """
    import json

    expression = _without_comments(expression).strip()
    if expression == "null": return None
    if expression == "true": return True
    if expression == "false": return False
    if expression in {"emptyList()", "mutableListOf()", "arrayListOf()"}: return []
    if expression in {"emptyMap()", "mutableMapOf()", "linkedMapOf()"}: return {}
    if expression == "emptySet()": return set()

    string = re.fullmatch(r'"((?:\\.|[^"\\])*)"', expression)
    if string:
        if "$" in expression:  # Kotlin string interpolation needs execution context.
            return _UNMODELED_DEFAULT
        try:
            return json.loads(expression)
        except json.JSONDecodeError:
            return _UNMODELED_DEFAULT

    number = re.fullmatch(r"[+-]?(?:0[xX][0-9a-fA-F_]+|(?:[0-9][0-9_]*)(?:\.[0-9_]*)?(?:[eE][+-]?[0-9_]+)?)[fFdDlL]?", expression)
    if number:
        cleaned = expression.replace("_", "")
        suffix = cleaned[-1:].lower()
        if suffix in {"f", "d", "l"}: cleaned = cleaned[:-1]
        try:
            if any(char in cleaned.lower() for char in (".", "e")):
                return float(cleaned)
            return int(cleaned, 0) if cleaned.lower().startswith(("0x", "+0x", "-0x")) else int(cleaned)
        except ValueError:
            return _UNMODELED_DEFAULT

    factory = re.fullmatch(r"(listOf|mutableListOf|arrayListOf|setOf|mutableSetOf)\s*\((.*)\)", expression, re.DOTALL)
    if factory:
        arguments = _split_top_level(factory.group(2)) if factory.group(2).strip() else []
        values = [_kotlin_default(argument, models, _seen) for argument, _ in arguments]
        if any(value is _UNMODELED_DEFAULT for value in values): return _UNMODELED_DEFAULT
        return set(values) if "set" in factory.group(1).lower() else values

    mapping = re.fullmatch(r"(mapOf|mutableMapOf|linkedMapOf)\s*\((.*)\)", expression, re.DOTALL)
    if mapping:
        result = {}
        contents = mapping.group(2).strip()
        for argument, _ in (_split_top_level(contents) if contents else []):
            pair = _split_top_level(argument, delimiter="=")
            if len(pair) != 2: return _UNMODELED_DEFAULT
            key = _kotlin_default(pair[0][0].strip(), models, _seen)
            value = _kotlin_default(pair[1][0].strip(), models, _seen)
            if key is _UNMODELED_DEFAULT or value is _UNMODELED_DEFAULT: return _UNMODELED_DEFAULT
            result[key] = value
        return result

    constructor = re.fullmatch(r"([A-Za-z_$][\w$]*)\s*\(\s*\)", expression)
    if constructor and models:
        class_name = constructor.group(1)
        nested_fields = models.get(class_name, [])
        if class_name in _seen or not nested_fields or not all(field.has_default for field in nested_fields):
            return _UNMODELED_DEFAULT
        nested: dict[str, Any] = {}
        next_seen = _seen | {class_name}
        for field in nested_fields:
            value = _kotlin_default(field.default_expression, models, next_seen)
            if value is _UNMODELED_DEFAULT:
                return _UNMODELED_DEFAULT
            nested[field.json_name] = value
        return nested
    return _UNMODELED_DEFAULT


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number_from_json(value: Any) -> float | int | None:
    from decimal import Decimal, InvalidOperation

    if _is_number(value):
        return value
    if isinstance(value, str):
        try:
            parsed = Decimal(value.strip())
            if parsed.is_finite():
                return int(parsed) if parsed == parsed.to_integral_value() else float(parsed)
        except (InvalidOperation, ValueError):
            return None
    return None


def _is_primitive(type_name: str) -> bool:
    return type_name in ("Int", "Long", "Short", "Byte", "Float", "Double", "Boolean")


def _missing_issue(field: KotlinField, *, explicit_null: bool, default: Any) -> ContractIssue | None:
    if field.nullable:
        return None
    type_name = field.type_name
    if type_name in ("List", "MutableList") or type_name.startswith(("List<", "MutableList<")):
        kind = "null-list" if explicit_null else "missing-list"
        detail = "Gson leaves the non-null Kotlin List as null; UI may crash when it iterates it"
    elif _is_primitive(type_name):
        kind = "silent-zero"
        detail = f"Gson leaves the non-null {type_name} at {default!r}; a missing/null wire value can display a false default"
    else:
        kind = "null-non-null" if explicit_null else "missing-non-null"
        detail = "Gson leaves the non-null reference field as null; later Kotlin use can throw NPE"
    return ContractIssue(field.name, kind, detail, field.line, field.source)


def decode(
    model: str,
    payload: dict[str, Any],
    models: dict[str, list[KotlinField]] | None = None,
) -> ContractResult:
    models = models or discover_models()
    fields = models.get(model, [])
    values: dict[str, Any] = {}
    issues: list[ContractIssue] = []
    # Kotlin emits a Java no-arg constructor only when every primary-constructor
    # parameter has a default. Gson calls it when present; otherwise it uses an
    # Unsafe allocator and absent fields start at JVM zero/null defaults.
    has_kotlin_no_arg_constructor = bool(fields) and all(field.has_default for field in fields)
    primitive_types = ("Int", "Long", "Short", "Byte", "Float", "Double", "Boolean")

    for field in fields:
        present = field.json_name in payload
        value = payload.get(field.json_name)
        type_name = field.type_name

        if not present:
            if has_kotlin_no_arg_constructor:
                default = _kotlin_default(field.default_expression, models)
                if default is _UNMODELED_DEFAULT:
                    issues.append(ContractIssue(
                        field.name, "unmodeled-default",
                        f"Gson invokes the Kotlin no-arg constructor, but simulator cannot evaluate default {field.default_expression!r}",
                        field.line, field.source,
                    ))
                    values[field.name] = None
                    continue
                values[field.name] = default
                if default is None:
                    missing = _missing_issue(field, explicit_null=False, default=default)
                    if missing:
                        issues.append(missing)
                continue

            default = _primitive_default(type_name)
            values[field.name] = default
            missing = _missing_issue(field, explicit_null=False, default=default)
            if missing:
                issues.append(missing)
            continue

        if value is None:
            if field.nullable:
                values[field.name] = None
                continue
            if type_name in primitive_types:
                # Gson's reflective adapter skips null assignment to Java primitive
                # fields, retaining either the constructor default or JVM zero.
                default = _kotlin_default(field.default_expression, models) if has_kotlin_no_arg_constructor else _primitive_default(type_name)
                if default is _UNMODELED_DEFAULT:
                    issues.append(ContractIssue(
                        field.name, "unmodeled-default",
                        f"null primitive retains unmodeled Kotlin default {field.default_expression!r}",
                        field.line, field.source,
                    ))
                    values[field.name] = None
                    continue
                values[field.name] = default
                issue = _missing_issue(field, explicit_null=True, default=default)
                if issue:
                    issues.append(issue)
                continue
            values[field.name] = None
            issue = _missing_issue(field, explicit_null=True, default=None)
            if issue:
                issues.append(issue)
            continue

        if type_name in ("Int", "Long", "Short", "Byte"):
            parsed = _number_from_json(value)
            minimum, maximum = {
                "Int": (-2147483648, 2147483647),
                "Long": (-9223372036854775808, 9223372036854775807),
                "Short": (-32768, 32767),
                "Byte": (-128, 127),
            }[type_name]
            if parsed is None or isinstance(parsed, float) or not minimum <= int(parsed) <= maximum:
                kind = "long-overflow" if type_name == "Long" and parsed is not None and (parsed < minimum or parsed > maximum) else "int-parse"
                detail = f"Gson cannot safely deserialize {value!r} as Kotlin {type_name}"
                issues.append(ContractIssue(field.name, kind, detail, field.line, field.source))
                values[field.name] = value
            else:
                values[field.name] = int(parsed)
            continue

        if type_name in ("Float", "Double"):
            parsed = _number_from_json(value)
            if parsed is None:
                issues.append(ContractIssue(field.name, "float-parse", f"Gson cannot deserialize {value!r} as Kotlin {type_name}", field.line, field.source))
                values[field.name] = value
            else:
                values[field.name] = float(parsed)
            continue

        if type_name == "Boolean":
            if isinstance(value, bool):
                values[field.name] = value
            elif isinstance(value, str):
                # Gson's Boolean adapter uses Boolean.parseBoolean for JSON strings.
                values[field.name] = value.lower() == "true"
            else:
                issues.append(ContractIssue(field.name, "type-mismatch", f"Gson cannot deserialize {type(value).__name__} as Boolean", field.line, field.source))
                values[field.name] = value
            continue

        if type_name == "Any":
            values[field.name] = value
            continue

        if type_name in ("String", "Char"):
            if isinstance(value, (dict, list)):
                issues.append(ContractIssue(field.name, "type-mismatch", f"Gson cannot deserialize JSON {type(value).__name__} as {type_name}", field.line, field.source))
            values[field.name] = value
            continue

        if type_name.startswith(("List<", "MutableList<")):
            if not isinstance(value, list):
                issues.append(ContractIssue(field.name, "type-mismatch", f"Gson expected JSON array for Kotlin {type_name}", field.line, field.source))
            values[field.name] = value
            continue

        if type_name.startswith(("Map<", "MutableMap<")):
            if not isinstance(value, dict):
                issues.append(ContractIssue(field.name, "type-mismatch", f"Gson expected JSON object for Kotlin {type_name}", field.line, field.source))
            values[field.name] = value
            continue

        values[field.name] = value
        if not isinstance(value, dict):
            issues.append(ContractIssue(field.name, "type-mismatch", f"Gson expected JSON object for Kotlin {type_name}", field.line, field.source))
    return ContractResult(model, values, issues)


def audit_payload(
    model: str,
    payload: dict[str, Any],
    models: dict[str, list[KotlinField]] | None = None,
    _depth: int = 0,
) -> list[ContractIssue]:
    models = models or discover_models()
    result = decode(model, payload, models)
    issues = list(result.issues)
    if _depth >= 12:
        return issues
    for field in models.get(model, []):
        value = payload.get(field.json_name)
        if value is None:
            continue
        type_name = field.type_name.rstrip("?")
        list_match = re.fullmatch(r"(?:List|MutableList)\s*<\s*([^<>?]+)\s*>", type_name)
        if list_match:
            child = list_match.group(1).strip()
            if child in models and isinstance(value, list):
                for index, item in enumerate(value):
                    if isinstance(item, dict):
                        issues.extend(
                            ContractIssue(f"{field.name}[{index}].{issue.field}", issue.kind, issue.detail, issue.line, issue.source)
                            for issue in audit_payload(child, item, models, _depth + 1)
                        )
        elif type_name in models and isinstance(value, dict):
            issues.extend(
                ContractIssue(f"{field.name}.{issue.field}", issue.kind, issue.detail, issue.line, issue.source)
                for issue in audit_payload(type_name, value, models, _depth + 1)
            )
    return issues
