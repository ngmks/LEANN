;   Copyright (c) Rich Hickey. All rights reserved.
;   The use and distribution terms for this software are covered by the
;   Eclipse Public License 1.0 (http://opensource.org/licenses/eclipse-1.0.php)
;   which can be found in the file epl-v10.html at the root of this distribution.
;   By using this software in any fashion, you are agreeing to be bound by
;   the terms of this license.
;   You must not remove this notice, or any other, from this software.

(ns ^{:doc "Clojure String utilities

It is poor form to (:use clojure.string). Instead, use require
with :as to specify a prefix, e.g.

(ns your.namespace.here
  (:require [clojure.string :as str]))

Design notes for clojure.string:

1. Strings are objects (as opposed to sequences). As such, the
   string being manipulated is the first argument to a function;
   passing nil will result in a NullPointerException unless
   documented otherwise. If you want sequence-y behavior instead,
   use a sequence.

2. Functions are generally not lazy, and call straight to host
   methods where those are available and efficient.

3. Functions take advantage of String implementation details to
   write high-performing loop/recurs instead of using higher-order
   functions. (This is not idiomatic in general-purpose application
   code.)

4. When a function is documented to accept a string argument, it
   will take any implementation of the correct *interface* on the
   host platform. In Java, this is CharSequence, which is more
   general than String. In ordinary usage you will almost always
   pass concrete strings. If you are doing something unusual,
   e.g. passing a mutable implementation of CharSequence, then
   thread-safety is your responsibility."
      :author "Stuart Sierra, Stuart Halloway, David Liebke"}
  clojure.string
  (:refer-clojure :exclude (replace reverse))
  (:import (java.util.regex Pattern Matcher)
           clojure.lang.LazilyPersistentVector))

(set! *warn-on-reflection* true)

(defn ^String reverse
  "Returns s with its characters reversed."
  {:added "1.2"}
  [^CharSequence s]
  (.toString (.reverse (StringBuilder. s))))

(defn ^String re-quote-replacement
  "Given a replacement string that you wish to be a literal
   replacement for a pattern match in replace or replace-first, do the
   necessary escaping of special characters in the replacement."
  {:added "1.5"}
  [^CharSequence replacement]
  (Matcher/quoteReplacement (.toString ^CharSequence replacement)))

(defn- replace-by
  [^CharSequence s re f]
  (let [m (re-matcher re s)]
    (if (.find m)
      (let [buffer (StringBuffer. (.length s))]
        (loop [found true]
          (if found
            (do (.appendReplacement m buffer (Matcher/quoteReplacement (f (re-groups m))))
                (recur (.find m)))
            (do (.appendTail m buffer)
                (.toString buffer)))))
      s)))

(defn ^String replace
  "Replaces all instance of match with replacement in s.

   match/replacement can be:

   string / string
   char / char
   pattern / (string or function of match).

   See also replace-first.

   The replacement is literal (i.e. none of its characters are treated
   specially) for all cases above except pattern / string.

   For pattern / string, $1, $2, etc. in the replacement string are
   substituted with the string that matched the corresponding
   parenthesized group in the pattern.  If you wish your replacement
   string r to be used literally, use (re-quote-replacement r) as the
   replacement argument.  See also documentation for
   java.util.regex.Matcher's appendReplacement method.

   Example:
   (clojure.string/replace \"Almost Pig Latin\" #\"\\b(\\w)(\\w+)\\b\" \"$2$1ay\")
   -> \"lmostAay igPay atinLay\""
  {:added "1.2"}
  [^CharSequence s match replacement]
  (let [s (.toString s)]
    (cond 
     (instance? Character match) (.replace s ^Character match ^Character replacement)
     (instance? CharSequence match) (.replace s ^CharSequence match ^CharSequence replacement)
     (instance? Pattern match) (if (instance? CharSequence replacement)
                                 (.replaceAll (re-matcher ^Pattern match s)
                                              (.toString ^CharSequence replacement))
                                 (replace-by s match replacement))
     :else (throw (IllegalArgumentException. (str "Invalid match arg: " match))))))

(defn- replace-first-by
  [^CharSequence s ^Pattern re f]
  (let [m (re-matcher re s)]
    (if (.find m)
      (let [buffer (StringBuffer. (.length s))
            rep (Matcher/quoteReplacement (f (re-groups m)))]
        (.appendReplacement m buffer rep)
        (.appendTail m buffer)
        (str buffer))
      s)))

(defn- replace-first-char
  [^CharSequence s ^Character match replace]
  (let [s (.toString s)
        i (.indexOf s (int match))]
    (if (= -1 i)
      s
      (str (subs s 0 i) replace (subs s (inc i))))))

(defn- replace-first-str
  [^CharSequence s ^String match ^String replace]
  (let [^String s (.toString s)
        i (.indexOf s match)]
    (if (= -1 i)
      s
      (str (subs s 0 i) replace (subs s (+ i (.length match)))))))

(defn ^String replace-first
  "Replaces the first instance of match with replacement in s.

   match/replacement can be:

   char / char
   string / string
   pattern / (string or function of match).

   See also replace.

   The replacement is literal (i.e. none of its characters are treated
   specially) for all cases above except pattern / string.

   For pattern / string, $1, $2, etc. in the replacement string are
   substituted with the string that matched the corresponding
   parenthesized group in the pattern.  If you wish your replacement
   string r to be used literally, use (re-quote-replacement r) as the
   replacement argument.  See also documentation for
   java.util.regex.Matcher's appendReplacement method.

   Example:
   (clojure.string/replace-first \"swap first two words\"
                                 #\"(\\w+)(\\s+)(\\w+)\" \"$3$2$1\")
   -> \"first swap two words\""
  {:added "1.2"}
  [^CharSequence s match replacement]
  (let [s (.toString s)]
    (cond
     (instance? Character match)
     (replace-first-char s match replacement)
     (instance? CharSequence match)
     (replace-first-str s (.toString ^CharSequence match)
                        (.toString ^CharSequence replacement))
     (instance? Pattern match)
     (if (instance? CharSequence replacement)
       (.replaceFirst (re-matcher ^Pattern match s)
                      (.toString ^CharSequence replacement))
       (replace-first-by s match replacement))
     :else (throw (IllegalArgumentException. (str "Invalid match arg: " match))))))


(defn ^String join
  "Returns a string of all elements in coll, as returned by (seq coll),
   separated by an optional separator."
  {:added "1.2"}
  ([coll]
     (apply str coll))
  ([separator coll]
     (loop [sb (StringBuilder. (str (first coll)))
            more (next coll)
            sep (str separator)]
       (if more
         (recur (-> sb (.append sep) (.append (str (first more))))
                (next more)
                sep)
         (str sb)))))

(defn ^String capitalize
  "Converts first character of the string to upper-case, all other
  characters to lower-case."
  {:added "1.2"}
  [^CharSequence s]
