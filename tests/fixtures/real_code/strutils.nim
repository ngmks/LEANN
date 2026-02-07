#
#
#            Nim's Runtime Library
#        (c) Copyright 2012 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

## The system module defines several common functions for working with strings,
## such as:
## * `$` for converting other data-types to strings
## * `&` for string concatenation
## * `add` for adding a new character or a string to the existing one
## * `in` (alias for `contains`) and `notin` for checking if a character
##   is in a string
##
## This module builds upon that, providing additional functionality in form of
## procedures, iterators and templates for strings.

runnableExamples:
  let
    numbers = @[867, 5309]
    multiLineString = "first line\nsecond line\nthird line"

  let jenny = numbers.join("-")
  assert jenny == "867-5309"

  assert splitLines(multiLineString) ==
         @["first line", "second line", "third line"]
  assert split(multiLineString) == @["first", "line", "second",
                                     "line", "third", "line"]
  assert indent(multiLineString, 4) ==
         "    first line\n    second line\n    third line"
  assert 'z'.repeat(5) == "zzzzz"

## The chaining of functions is possible thanks to the
## `method call syntax<manual.html#procedures-method-call-syntax>`_:

runnableExamples:
  from std/sequtils import map

  let jenny = "867-5309"
  assert jenny.split('-').map(parseInt) == @[867, 5309]

  assert "Beetlejuice".indent(1).repeat(3).strip ==
         "Beetlejuice Beetlejuice Beetlejuice"

## This module is available for the `JavaScript target
## <backends.html#backends-the-javascript-target>`_.
##
## ----
##
## **See also:**
## * `strformat module<strformat.html>`_ for string interpolation and formatting
## * `unicode module<unicode.html>`_ for Unicode UTF-8 handling
## * `sequtils module<sequtils.html>`_ for operations on container
##   types (including strings)
## * `parsecsv module<parsecsv.html>`_ for a high-performance CSV parser
## * `parseutils module<parseutils.html>`_ for lower-level parsing of tokens,
##   numbers, identifiers, etc.
## * `parseopt module<parseopt.html>`_ for command-line parsing
## * `pegs module<pegs.html>`_ for PEG (Parsing Expression Grammar) support
## * `strtabs module<strtabs.html>`_ for efficient hash tables
##   (dictionaries, in some programming languages) mapping from strings to strings
## * `ropes module<ropes.html>`_ for rope data type, which can represent very
##   long strings efficiently
## * `re module<re.html>`_ for regular expression (regex) support
## * `strscans<strscans.html>`_ for `scanf` and `scanp` macros, which offer
##   easier substring extraction than regular expressions


import std/parseutils
from std/math import pow, floor, log10
from std/algorithm import fill, reverse
import std/enumutils
from std/bitops import fastLog2

from std/unicode import toLower, toUpper
export toLower, toUpper

include "system/inclrtl"
import std/private/[since, jsutils]
from std/private/strimpl import cmpIgnoreStyleImpl, cmpIgnoreCaseImpl,
    startsWithImpl, endsWithImpl

when defined(nimPreviewSlimSystem):
  import std/assertions


const
  Whitespace* = {' ', '\t', '\v', '\r', '\l', '\f'}
    ## All the characters that count as whitespace (space, tab, vertical tab,
    ## carriage return, new line, form feed).

  Letters* = {'A'..'Z', 'a'..'z'}
    ## The set of letters.

  UppercaseLetters* = {'A'..'Z'}
    ## The set of uppercase ASCII letters.

  LowercaseLetters* = {'a'..'z'}
    ## The set of lowercase ASCII letters.

  PunctuationChars* = {'!'..'/', ':'..'@', '['..'`', '{'..'~'}
    ## The set of all ASCII punctuation characters.

  Digits* = {'0'..'9'}
    ## The set of digits.

  HexDigits* = {'0'..'9', 'A'..'F', 'a'..'f'}
    ## The set of hexadecimal digits.

  IdentChars* = {'a'..'z', 'A'..'Z', '0'..'9', '_'}
    ## The set of characters an identifier can consist of.

  IdentStartChars* = {'a'..'z', 'A'..'Z', '_'}
    ## The set of characters an identifier can start with.

  Newlines* = {'\13', '\10'}
    ## The set of characters a newline terminator can start with (carriage
    ## return, line feed).

  PrintableChars* = Letters + Digits + PunctuationChars + Whitespace
    ## The set of all printable ASCII characters (letters, digits, whitespace, and punctuation characters).

  AllChars* = {'\x00'..'\xFF'}
    ## A set with all the possible characters.
    ##
    ## Not very useful by its own, you can use it to create *inverted* sets to
    ## make the `find func<#find,string,set[char],Natural,int>`_
    ## find **invalid** characters in strings. Example:
    ##   ```nim
    ##   let invalid = AllChars - Digits
    ##   doAssert "01234".find(invalid) == -1
    ##   doAssert "01A34".find(invalid) == 2
    ##   ```

func isAlphaAscii*(c: char): bool {.rtl, extern: "nsuIsAlphaAsciiChar".} =
  ## Checks whether or not character `c` is alphabetical.
  ##
  ## This checks a-z, A-Z ASCII characters only.
  ## Use `Unicode module<unicode.html>`_ for UTF-8 support.
  runnableExamples:
    doAssert isAlphaAscii('e') == true
    doAssert isAlphaAscii('E') == true
    doAssert isAlphaAscii('8') == false
  return c in Letters

func isAlphaNumeric*(c: char): bool {.rtl, extern: "nsuIsAlphaNumericChar".} =
  ## Checks whether or not `c` is alphanumeric.
  ##
  ## This checks a-z, A-Z, 0-9 ASCII characters only.
  runnableExamples:
    doAssert isAlphaNumeric('n') == true
    doAssert isAlphaNumeric('8') == true
    doAssert isAlphaNumeric(' ') == false
  return c in Letters+Digits

func isDigit*(c: char): bool {.rtl, extern: "nsuIsDigitChar".} =
  ## Checks whether or not `c` is a number.
  ##
  ## This checks 0-9 ASCII characters only.
  runnableExamples:
    doAssert isDigit('n') == false
    doAssert isDigit('8') == true
  return c in Digits

func isSpaceAscii*(c: char): bool {.rtl, extern: "nsuIsSpaceAsciiChar".} =
  ## Checks whether or not `c` is a whitespace character.
  runnableExamples:
    doAssert isSpaceAscii('n') == false
    doAssert isSpaceAscii(' ') == true
    doAssert isSpaceAscii('\t') == true
  return c in Whitespace

func isLowerAscii*(c: char): bool {.rtl, extern: "nsuIsLowerAsciiChar".} =
  ## Checks whether or not `c` is a lower case character.
  ##
  ## This checks ASCII characters only.
  ## Use `Unicode module<unicode.html>`_ for UTF-8 support.
  ##
  ## See also:
  ## * `toLowerAscii func<#toLowerAscii,char>`_
  runnableExamples:
    doAssert isLowerAscii('e') == true
    doAssert isLowerAscii('E') == false
    doAssert isLowerAscii('7') == false
  return c in LowercaseLetters

func isUpperAscii*(c: char): bool {.rtl, extern: "nsuIsUpperAsciiChar".} =
  ## Checks whether or not `c` is an upper case character.
  ##
  ## This checks ASCII characters only.
  ## Use `Unicode module<unicode.html>`_ for UTF-8 support.
  ##
  ## See also:
  ## * `toUpperAscii func<#toUpperAscii,char>`_
  runnableExamples:
    doAssert isUpperAscii('e') == false
