//===----------------------------------------------------------------------===//
//
// This source file is part of the Swift.org open source project
//
// Copyright (c) 2014 - 2024 Apple Inc. and the Swift project authors
// Licensed under Apache License v2.0 with Runtime Library Exception
//
// See https://swift.org/LICENSE.txt for license information
// See https://swift.org/CONTRIBUTORS.txt for the list of Swift project authors
//
//===----------------------------------------------------------------------===//

import SwiftShims

/// A Unicode string value that is a collection of characters.
///
/// A string is a series of characters, such as `"Swift"`, that forms a
/// collection. Strings in Swift are Unicode correct and locale insensitive,
/// and are designed to be efficient. The `String` type bridges with the
/// Objective-C class `NSString` and offers interoperability with C functions
/// that works with strings.
///
/// You can create new strings using string literals or string interpolations.
/// A *string literal* is a series of characters enclosed in quotes.
///
///     let greeting = "Welcome!"
///
/// *String interpolations* are string literals that evaluate any included
/// expressions and convert the results to string form. String interpolations
/// give you an easy way to build a string from multiple pieces. Wrap each
/// expression in a string interpolation in parentheses, prefixed by a
/// backslash.
///
///     let name = "Rosa"
///     let personalizedGreeting = "Welcome, \(name)!"
///     // personalizedGreeting == "Welcome, Rosa!"
///
///     let price = 2
///     let number = 3
///     let cookiePrice = "\(number) cookies: $\(price * number)."
///     // cookiePrice == "3 cookies: $6."
///
/// Combine strings using the concatenation operator (`+`).
///
///     let longerGreeting = greeting + " We're glad you're here!"
///     // longerGreeting == "Welcome! We're glad you're here!"
///
/// Multiline string literals are enclosed in three double quotation marks
/// (`"""`), with each delimiter on its own line. Indentation is stripped from
/// each line of a multiline string literal to match the indentation of the
/// closing delimiter.
///
///     let banner = """
///               __,
///              (           o  /) _/_
///               `.  , , , ,  //  /
///             (___)(_(_/_(_ //_ (__
///                          /)
///                         (/
///             """
///
/// Modifying and Comparing Strings
/// ===============================
///
/// Strings always have value semantics. Modifying a copy of a string leaves
/// the original unaffected.
///
///     var otherGreeting = greeting
///     otherGreeting += " Have a nice time!"
///     // otherGreeting == "Welcome! Have a nice time!"
///
///     print(greeting)
///     // Prints "Welcome!"
///
/// Comparing strings for equality using the equal-to operator (`==`) or a
/// relational operator (like `<` or `>=`) is always performed using Unicode
/// canonical representation. As a result, different representations of a
/// string compare as being equal.
///
///     let cafe1 = "Cafe\u{301}"
///     let cafe2 = "Café"
///     print(cafe1 == cafe2)
///     // Prints "true"
///
/// The Unicode scalar value `"\u{301}"` modifies the preceding character to
/// include an accent, so `"e\u{301}"` has the same canonical representation
/// as the single Unicode scalar value `"é"`.
///
/// Basic string operations are not sensitive to locale settings, ensuring that
/// string comparisons and other operations always have a single, stable
/// result, allowing strings to be used as keys in `Dictionary` instances and
/// for other purposes.
///
/// Accessing String Elements
/// =========================
///
/// A string is a collection of *extended grapheme clusters*, which approximate
/// human-readable characters. Many individual characters, such as "é", "김",
/// and "🇮🇳", can be made up of multiple Unicode scalar values. These scalar
/// values are combined by Unicode's boundary algorithms into extended
/// grapheme clusters, represented by the Swift `Character` type. Each element
/// of a string is represented by a `Character` instance.
///
/// For example, to retrieve the first word of a longer string, you can search
/// for a space and then create a substring from a prefix of the string up to
/// that point:
///
///     let name = "Marie Curie"
///     let firstSpace = name.firstIndex(of: " ") ?? name.endIndex
///     let firstName = name[..<firstSpace]
///     // firstName == "Marie"
///
/// The `firstName` constant is an instance of the `Substring` type---a type
/// that represents substrings of a string while sharing the original string's
/// storage. Substrings present the same interface as strings.
///
///     print("\(name)'s first name has \(firstName.count) letters.")
///     // Prints "Marie Curie's first name has 5 letters."
///
/// Accessing a String's Unicode Representation
/// ===========================================
///
/// If you need to access the contents of a string as encoded in different
/// Unicode encodings, use one of the string's `unicodeScalars`, `utf16`, or
/// `utf8` properties. Each property provides access to a view of the string
/// as a series of code units, each encoded in a different Unicode encoding.
///
/// To demonstrate the different views available for every string, the
/// following examples use this `String` instance:
///
///     let cafe = "Cafe\u{301} du 🌍"
///     print(cafe)
///     // Prints "Café du 🌍"
///
/// The `cafe` string is a collection of the nine characters that are visible
/// when the string is displayed.
///
///     print(cafe.count)
///     // Prints "9"
///     print(Array(cafe))
///     // Prints "["C", "a", "f", "é", " ", "d", "u", " ", "🌍"]"
///
/// Unicode Scalar View
/// -------------------
///
/// A string's `unicodeScalars` property is a collection of Unicode scalar
/// values, the 21-bit codes that are the basic unit of Unicode. Each scalar
/// value is represented by a `Unicode.Scalar` instance and is equivalent to a
/// UTF-32 code unit.
///
///     print(cafe.unicodeScalars.count)
///     // Prints "10"
///     print(Array(cafe.unicodeScalars))
///     // Prints "["C", "a", "f", "e", "\u{0301}", " ", "d", "u", " ", "\u{0001F30D}"]"
///     print(cafe.unicodeScalars.map { $0.value })
///     // Prints "[67, 97, 102, 101, 769, 32, 100, 117, 32, 127757]"
///
/// The `unicodeScalars` view's elements comprise each Unicode scalar value in
/// the `cafe` string. In particular, because `cafe` was declared using the
/// decomposed form of the `"é"` character, `unicodeScalars` contains the
/// scalar values for both the letter `"e"` (101) and the accent character
/// `"´"` (769).
///
/// UTF-16 View
/// -----------
///
/// A string's `utf16` property is a collection of UTF-16 code units, the
/// 16-bit encoding form of the string's Unicode scalar values. Each code unit
/// is stored as a `UInt16` instance.
///
///     print(cafe.utf16.count)
///     // Prints "11"
///     print(Array(cafe.utf16))
///     // Prints "[67, 97, 102, 101, 769, 32, 100, 117, 32, 55356, 57101]"
///
/// The elements of the `utf16` view are the code units for the string when
/// encoded in UTF-16. These elements match those accessed through indexed
/// `NSString` APIs.
///
///     let nscafe = cafe as NSString
///     print(nscafe.length)
///     // Prints "11"
///     print(nscafe.character(at: 3))
///     // Prints "101"
///
/// UTF-8 View
/// ----------
///
/// A string's `utf8` property is a collection of UTF-8 code units, the 8-bit
/// encoding form of the string's Unicode scalar values. Each code unit is
/// stored as a `UInt8` instance.
///
///     print(cafe.utf8.count)
///     // Prints "14"
///     print(Array(cafe.utf8))
///     // Prints "[67, 97, 102, 101, 204, 129, 32, 100, 117, 32, 240, 159, 140, 141]"
///
/// The elements of the `utf8` view are the code units for the string when
/// encoded in UTF-8. This representation matches the one used when `String`
/// instances are passed to C APIs.
