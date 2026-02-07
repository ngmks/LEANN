// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System.Buffers;
using System.Collections;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.Globalization;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;

namespace System
{
    // The String class represents a static string of characters.  Many of
    // the string methods perform some type of transformation on the current
    // instance and return the result as a new string.  As with arrays, character
    // positions (indices) are zero-based.

    [Serializable]
    [NonVersionable] // This only applies to field layout
    [TypeForwardedFrom("mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089")]
    public sealed partial class String
        : IComparable,
          IEnumerable,
          IConvertible,
          IEnumerable<char>,
          IComparable<string?>,
          IEquatable<string?>,
          ICloneable,
          ISpanParsable<string>
    {
        /// <summary>Maximum length allowed for a string.</summary>
        /// <remarks>Keep in sync with AllocateString in gchelpers.cpp.</remarks>
        internal const int MaxLength = 0x3FFFFFDF;

#if !NATIVEAOT
        // The Empty constant holds the empty string value. It is initialized by the EE during startup.
        // It is treated as intrinsic by the JIT as so the static constructor would never run.
        // Leaving it uninitialized would confuse debuggers.
#pragma warning disable CS8618 // compiler sees this non-nullable static string as uninitialized
        [Intrinsic]
        public static readonly string Empty;
#pragma warning restore CS8618
#endif

        //
        // These fields map directly onto the fields in an EE StringObject.  See object.h for the layout.
        //
        [NonSerialized]
        private readonly int _stringLength;

        // For empty strings, _firstChar will be '\0', since strings are both null-terminated and length-prefixed.
        // The field is also read-only, however String uses .ctors that C# doesn't recognise as .ctors,
        // so trying to mark the field as 'readonly' causes the compiler to complain.
        [NonSerialized]
        private char _firstChar;

        /*
         * CONSTRUCTORS
         *
         * Defining a new constructor for string-like types (like String) requires changes both
         * to the managed code below and to the native VM code. See the comment at the top of
         * src/vm/ecall.cpp for instructions on how to add new overloads.
         */

        [MethodImpl(MethodImplOptions.InternalCall)]
#if MONO
        [DynamicDependency("Ctor(System.Char[])")]
#endif
        public extern String(char[]? value);

        private static string Ctor(char[]? value)
        {
            if (value == null || value.Length == 0)
                return Empty;

            string result = FastAllocateString(value.Length);

            Buffer.Memmove(
                elementCount: (uint)result.Length, // derefing Length now allows JIT to prove 'result' not null below
                destination: ref result._firstChar,
                source: ref MemoryMarshal.GetArrayDataReference(value));

            return result;
        }

        [MethodImpl(MethodImplOptions.InternalCall)]
#if MONO
        [DynamicDependency("Ctor(System.Char[],System.Int32,System.Int32)")]
#endif
        public extern String(char[] value, int startIndex, int length);

        private static string Ctor(char[] value, int startIndex, int length)
        {
            ArgumentNullException.ThrowIfNull(value);
            ArgumentOutOfRangeException.ThrowIfNegative(startIndex);
            ArgumentOutOfRangeException.ThrowIfNegative(length);
            ArgumentOutOfRangeException.ThrowIfGreaterThan(startIndex, value.Length - length);

            if (length == 0)
                return Empty;

            string result = FastAllocateString(length);

            Buffer.Memmove(
                elementCount: (uint)result.Length, // derefing Length now allows JIT to prove 'result' not null below
                destination: ref result._firstChar,
                source: ref Unsafe.Add(ref MemoryMarshal.GetArrayDataReference(value), startIndex));

            return result;
        }

        [CLSCompliant(false)]
        [MethodImpl(MethodImplOptions.InternalCall)]
#if MONO
        [DynamicDependency("Ctor(System.Char*)")]
#endif
        public extern unsafe String(char* value);

        private static unsafe string Ctor(char* ptr)
        {
            if (ptr == null)
                return Empty;

            int count = wcslen(ptr);
            if (count == 0)
                return Empty;

            string result = FastAllocateString(count);

            Buffer.Memmove(
                elementCount: (uint)result.Length, // derefing Length now allows JIT to prove 'result' not null below
                destination: ref result._firstChar,
                source: ref *ptr);

            return result;
        }

        [CLSCompliant(false)]
        [MethodImpl(MethodImplOptions.InternalCall)]
#if MONO
        [DynamicDependency("Ctor(System.Char*,System.Int32,System.Int32)")]
#endif
        public extern unsafe String(char* value, int startIndex, int length);

        private static unsafe string Ctor(char* ptr, int startIndex, int length)
        {
            ArgumentOutOfRangeException.ThrowIfNegative(length);
            ArgumentOutOfRangeException.ThrowIfNegative(startIndex);

            char* pStart = ptr + startIndex;

            // overflow check
            if (pStart < ptr)
                throw new ArgumentOutOfRangeException(nameof(startIndex), SR.ArgumentOutOfRange_PartialWCHAR);

            if (length == 0)
                return Empty;

            if (ptr == null)
                throw new ArgumentOutOfRangeException(nameof(ptr), SR.ArgumentOutOfRange_PartialWCHAR);

            string result = FastAllocateString(length);

            Buffer.Memmove(
               elementCount: (uint)result.Length, // derefing Length now allows JIT to prove 'result' not null below
               destination: ref result._firstChar,
               source: ref *pStart);

            return result;
        }

        [CLSCompliant(false)]
        [MethodImpl(MethodImplOptions.InternalCall)]
#if MONO
        [DynamicDependency("Ctor(System.SByte*)")]
#endif
        public extern unsafe String(sbyte* value);

        private static unsafe string Ctor(sbyte* value)
        {
            byte* pb = (byte*)value;
            if (pb == null)
                return Empty;

            int numBytes = strlen((byte*)value);

            return CreateStringForSByteConstructor(pb, numBytes);
        }

        [CLSCompliant(false)]
        [MethodImpl(MethodImplOptions.InternalCall)]
#if MONO
        [DynamicDependency("Ctor(System.SByte*,System.Int32,System.Int32)")]
#endif
        public extern unsafe String(sbyte* value, int startIndex, int length);
