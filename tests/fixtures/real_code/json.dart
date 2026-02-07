// Copyright (c) 2013, the Dart project authors.  Please see the AUTHORS file
// for details. All rights reserved. Use of this source code is governed by a
// BSD-style license that can be found in the LICENSE file.

part of "dart:convert";

/// Error thrown by JSON serialization if an object cannot be serialized.
///
/// The [unsupportedObject] field holds that object that failed to be serialized.
///
/// If an object isn't directly serializable, the serializer calls the `toJson`
/// method on the object. If that call fails, the error will be stored in the
/// [cause] field. If the call returns an object that isn't directly
/// serializable, the [cause] is null.
class JsonUnsupportedObjectError extends Error {
  /// The object that could not be serialized.
  final Object? unsupportedObject;

  /// The exception thrown when trying to convert the object.
  final Object? cause;

  /// The partial result of the conversion, up until the error happened.
  ///
  /// May be null.
  final String? partialResult;

  JsonUnsupportedObjectError(
    this.unsupportedObject, {
    this.cause,
    this.partialResult,
  });

  String toString() {
    var safeString = Error.safeToString(unsupportedObject);
    String prefix;
    if (cause != null) {
      prefix = "Converting object to an encodable object failed:";
    } else {
      prefix = "Converting object did not return an encodable object:";
    }
    return "$prefix $safeString";
  }
}

/// Reports that an object could not be stringified due to cyclic references.
///
/// An object that references itself cannot be serialized by
/// [JsonCodec.encode]/[JsonEncoder.convert].
/// When the cycle is detected, a [JsonCyclicError] is thrown.
class JsonCyclicError extends JsonUnsupportedObjectError {
  /// The first object that was detected as part of a cycle.
  JsonCyclicError(super.object);
  String toString() => "Cyclic error in JSON stringify";
}

/// An instance of the default implementation of the [JsonCodec].
///
/// This instance provides a convenient access to the most common JSON
/// use cases.
///
/// Examples:
/// ```dart
/// var encoded = json.encode([1, 2, { "a": null }]);
/// var decoded = json.decode('["foo", { "bar": 499 }]');
/// ```
/// The top-level [jsonEncode] and [jsonDecode] functions may be used instead if
/// a local variable shadows the [json] constant.
const JsonCodec json = JsonCodec();

/// Converts [object] to a JSON string.
///
/// If value contains objects that are not directly encodable to a JSON
/// string (a value that is not a number, boolean, string, null, list or a map
/// with string keys), the [toEncodable] function is used to convert it to an
/// object that must be directly encodable.
///
/// If [toEncodable] is omitted, it defaults to a function that returns the
/// result of calling `.toJson()` on the unencodable object.
///
/// Shorthand for `json.encode`. Useful if a local variable shadows the global
/// [json] constant.
///
/// Example:
/// ```dart
/// const data = {'text': 'foo', 'value': 2, 'status': false, 'extra': null};
/// final String jsonString = jsonEncode(data);
/// print(jsonString); // {"text":"foo","value":2,"status":false,"extra":null}
/// ```
///
/// Example of converting an otherwise unsupported object to a
/// custom JSON format:
///
/// ```dart
/// class CustomClass {
///   final String text;
///   final int value;
///   CustomClass({required this.text, required this.value});
///   CustomClass.fromJson(Map<String, dynamic> json)
///       : text = json['text'],
///         value = json['value'];
///
///   static Map<String, dynamic> toJson(CustomClass value) =>
///       {'text': value.text, 'value': value.value};
/// }
///
/// void main() {
///   final CustomClass cc = CustomClass(text: 'Dart', value: 123);
///   final jsonText = jsonEncode({'cc': cc},
///       toEncodable: (Object? value) => value is CustomClass
///           ? CustomClass.toJson(value)
///           : throw UnsupportedError('Cannot convert to JSON: $value'));
///   print(jsonText); // {"cc":{"text":"Dart","value":123}}
/// }
/// ```
String jsonEncode(
  Object? object, {
  Object? Function(Object? nonEncodable)? toEncodable,
}) => json.encode(object, toEncodable: toEncodable);

/// Parses the string and returns the resulting Json object.
///
/// The optional [reviver] function is called once for each object or list
/// property that has been parsed during decoding. The `key` argument is either
/// the integer list index for a list property, the string map key for object
/// properties, or `null` for the final result.
///
/// The default [reviver] (when not provided) is the identity function.
///
/// Shorthand for `json.decode`. Useful if a local variable shadows the global
/// [json] constant.
///
/// Example:
/// ```dart
/// const jsonString =
///     '{"text": "foo", "value": 1, "status": false, "extra": null}';
///
/// final data = jsonDecode(jsonString);
/// print(data['text']); // foo
/// print(data['value']); // 1
/// print(data['status']); // false
/// print(data['extra']); // null
///
/// const jsonArray = '''
///   [{"text": "foo", "value": 1, "status": true},
///    {"text": "bar", "value": 2, "status": false}]
/// ''';
///
/// final List<dynamic> dataList = jsonDecode(jsonArray);
/// print(dataList[0]); // {text: foo, value: 1, status: true}
/// print(dataList[1]); // {text: bar, value: 2, status: false}
///
/// final item = dataList[0];
/// print(item['text']); // foo
/// print(item['value']); // 1
/// print(item['status']); // false
/// ```
dynamic jsonDecode(
  String source, {
  Object? Function(Object? key, Object? value)? reviver,
}) => json.decode(source, reviver: reviver);

/// A [JsonCodec] encodes JSON objects to strings and decodes strings to
/// JSON objects.
///
/// Examples:
/// ```dart
/// var encoded = json.encode([1, 2, { "a": null }]);
/// var decoded = json.decode('["foo", { "bar": 499 }]');
/// ```
final class JsonCodec extends Codec<Object?, String> {
  final Object? Function(Object? key, Object? value)? _reviver;
  final Object? Function(dynamic)? _toEncodable;

  /// Creates a `JsonCodec` with the given reviver and encoding function.
  ///
  /// The [reviver] function is called during decoding. It is invoked once for
  /// each object or list property that has been parsed.
  /// The `key` argument is either the integer list index for a list property,
  /// the string map key for object properties, or `null` for the final result.
  ///
  /// If [reviver] is omitted, it defaults to returning the value argument.
  ///
  /// The [toEncodable] function is used during encoding. It is invoked for
  /// values that are not directly encodable to a string (a value that is not a
  /// number, boolean, string, null, list or a map with string keys). The
  /// function must return an object that is directly encodable. The elements of
  /// a returned list and values of a returned map do not need to be directly
  /// encodable, and if they aren't, `toEncodable` will be used on them as well.
  /// Please notice that it is possible to cause an infinite recursive regress
  /// in this way, by effectively creating an infinite data structure through
  /// repeated call to `toEncodable`.
  ///
  /// If [toEncodable] is omitted, it defaults to a function that returns the
  /// result of calling `.toJson()` on the unencodable object.
  const JsonCodec({
    Object? Function(Object? key, Object? value)? reviver,
    Object? Function(dynamic object)? toEncodable,
  }) : _reviver = reviver,
       _toEncodable = toEncodable;

