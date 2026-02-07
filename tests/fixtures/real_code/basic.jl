# This file is a part of Julia. License is MIT: https://julialang.org/license

import Core: Symbol

"""
The `AbstractString` type is the supertype of all string implementations in
Julia. Strings are encodings of sequences of [Unicode](https://unicode.org/)
code points as represented by the `AbstractChar` type. Julia makes a few assumptions
about strings:

* Strings are encoded in terms of fixed-size "code units"
  * Code units can be extracted with `codeunit(s, i)`
  * The first code unit has index `1`
  * The last code unit has index `ncodeunits(s)`
  * Any index `i` such that `1 ≤ i ≤ ncodeunits(s)` is in bounds
* String indexing is done in terms of these code units:
  * Characters are extracted by `s[i]` with a valid string index `i`
  * Each `AbstractChar` in a string is encoded by one or more code units
  * Only the index of the first code unit of an `AbstractChar` is a valid index
  * The encoding of an `AbstractChar` is independent of what precedes or follows it
  * String encodings are [self-synchronizing](https://en.wikipedia.org/wiki/Self-synchronizing_code) – i.e. `isvalid(s, i)` is O(1)

Some string functions that extract code units, characters or substrings from
strings error if you pass them out-of-bounds or invalid string indices. This
includes `codeunit(s, i)` and `s[i]`. Functions that do string
index arithmetic take a more relaxed approach to indexing and give you the
closest valid string index when in-bounds, or when out-of-bounds, behave as if
there were an infinite number of characters padding each side of the string.
Usually these imaginary padding characters have code unit length `1` but string
types may choose different "imaginary" character sizes as makes sense for their
implementations (e.g. substrings may pass index arithmetic through to the
underlying string they provide a view into). Relaxed indexing functions include
those intended for index arithmetic: `thisind`, `nextind` and `prevind`. This
model allows index arithmetic to work with out-of-bounds indices as
intermediate values so long as one never uses them to retrieve a character,
which often helps avoid needing to code around edge cases.

See also [`codeunit`](@ref), [`ncodeunits`](@ref), [`thisind`](@ref),
[`nextind`](@ref), [`prevind`](@ref).
"""
AbstractString

## required string functions ##

"""
    ncodeunits(s::AbstractString)::Int

Return the number of code units in a string. Indices that are in bounds to
access this string must satisfy `1 ≤ i ≤ ncodeunits(s)`. Not all such indices
are valid – they may not be the start of a character, but they will return a
code unit value when calling `codeunit(s,i)`.

# Examples
```jldoctest
julia> ncodeunits("The Julia Language")
18

julia> ncodeunits("∫eˣ")
6

julia> ncodeunits('∫'), ncodeunits('e'), ncodeunits('ˣ')
(3, 1, 2)
```

See also [`codeunit`](@ref), [`checkbounds`](@ref), [`sizeof`](@ref),
[`length`](@ref), [`lastindex`](@ref).
"""
ncodeunits(s::AbstractString)

"""
    codeunit(s::AbstractString)::Type{<:Union{UInt8, UInt16, UInt32}}

Return the code unit type of the given string object. For ASCII, Latin-1, or
UTF-8 encoded strings, this would be `UInt8`; for UCS-2 and UTF-16 it would be
`UInt16`; for UTF-32 it would be `UInt32`. The code unit type need not be
limited to these three types, but it's hard to think of widely used string
encodings that don't use one of these units. `codeunit(s)` is the same as
`typeof(codeunit(s,1))` when `s` is a non-empty string.

See also [`ncodeunits`](@ref).
"""
codeunit(s::AbstractString)

const CodeunitType = Union{Type{UInt8},Type{UInt16},Type{UInt32}}

"""
    codeunit(s::AbstractString, i::Integer)::Union{UInt8, UInt16, UInt32}

Return the code unit value in the string `s` at index `i`. Note that

    codeunit(s, i) :: codeunit(s)

I.e. the value returned by `codeunit(s, i)` is of the type returned by
`codeunit(s)`.

# Examples
```jldoctest
julia> a = codeunit("Hello", 2)
0x65

julia> typeof(a)
UInt8
```

See also [`ncodeunits`](@ref), [`checkbounds`](@ref).
"""
@propagate_inbounds codeunit(s::AbstractString, i::Integer) = i isa Int ?
    throw(MethodError(codeunit, (s, i))) : codeunit(s, Int(i)::Int)

"""
    isvalid(s::AbstractString, i::Integer)::Bool

Predicate indicating whether the given index is the start of the encoding of a
character in `s` or not. If `isvalid(s, i)` is true then `s[i]` will return the
character whose encoding starts at that index, if it's false, then `s[i]` will
raise an invalid index error or a bounds error depending on if `i` is in bounds.
In order for `isvalid(s, i)` to be an O(1) function, the encoding of `s` must be
[self-synchronizing](https://en.wikipedia.org/wiki/Self-synchronizing_code). This
is a basic assumption of Julia's generic string support.

See also [`getindex`](@ref), [`iterate`](@ref), [`thisind`](@ref),
[`nextind`](@ref), [`prevind`](@ref), [`length`](@ref).

# Examples
```jldoctest
julia> str = "αβγdef";

julia> isvalid(str, 1)
true

julia> str[1]
'α': Unicode U+03B1 (category Ll: Letter, lowercase)

julia> isvalid(str, 2)
false

julia> str[2]
ERROR: StringIndexError: invalid index [2], valid nearby indices [1]=>'α', [3]=>'β'
Stacktrace:
[...]
```
"""
@propagate_inbounds isvalid(s::AbstractString, i::Integer) = i isa Int ?
    throw(MethodError(isvalid, (s, i))) : isvalid(s, Int(i)::Int)

"""
    iterate(s::AbstractString, i::Integer)::Union{Tuple{<:AbstractChar, Int}, Nothing}

Return a tuple of the character in `s` at index `i` with the index of the start
of the following character in `s`. This is the key method that allows strings to
be iterated, yielding a sequences of characters. The `iterate` function, as part
of the iteration protocol may assume that `i` is the start of a character in `s`.

See also [`getindex`](@ref), [`checkbounds`](@ref).
"""
@propagate_inbounds iterate(s::AbstractString, i::Integer) = i isa Int ?
    throw(MethodError(iterate, (s, i))) : iterate(s, Int(i)::Int)

## basic generic definitions ##

eltype(::Type{<:AbstractString}) = Char # some string types may use another AbstractChar

"""
    sizeof(str::AbstractString)

Size, in bytes, of the string `str`. Equal to the number of code units in `str` multiplied by
the size, in bytes, of one code unit in `str`.

# Examples
```jldoctest
julia> sizeof("")
0

julia> sizeof("∀")
3
```
"""
sizeof(s::AbstractString) = ncodeunits(s)::Int * sizeof(codeunit(s)::CodeunitType)
firstindex(s::AbstractString) = 1
lastindex(s::AbstractString) = thisind(s, ncodeunits(s)::Int)
isempty(s::AbstractString) = iszero(ncodeunits(s)::Int)

@propagate_inbounds first(s::AbstractString) = s[firstindex(s)]

function getindex(s::AbstractString, i::Integer)
    @boundscheck checkbounds(s, i)
    @inbounds return isvalid(s, i) ? (iterate(s, i)::NTuple{2,Any})[1] : string_index_err(s, i)
end

getindex(s::AbstractString, i::Colon) = s
# TODO: handle other ranges with stride ±1 specially?
# TODO: add more @propagate_inbounds annotations?
getindex(s::AbstractString, v::AbstractVector{<:Integer}) =
    sprint(io->(for i in v; write(io, s[i]) end), sizehint=length(v))
getindex(s::AbstractString, v::AbstractVector{Bool}) =
    throw(ArgumentError("logical indexing not supported for strings"))

function get(s::AbstractString, i::Integer, default)
    checkbounds(Bool, s, i) ? (@inbounds s[i]) : default
end
