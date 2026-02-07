//     __ _____ _____ _____
//  __|  |   __|     |   | |  JSON for Modern C++
// |  |  |__   |  |  | | | |  version 3.12.0
// |_____|_____|_____|_|___|  https://github.com/nlohmann/json
//
// SPDX-FileCopyrightText: 2013-2026 Niels Lohmann <https://nlohmann.me>
// SPDX-License-Identifier: MIT

/****************************************************************************\
 * Note on documentation: The source files contain links to the online      *
 * documentation of the public API at https://json.nlohmann.me. This URL    *
 * contains the most recent documentation and should also be applicable to  *
 * previous versions; documentation for deprecated functions is not         *
 * removed, but marked deprecated. See "Generate documentation" section in  *
 * file docs/README.md.                                                     *
\****************************************************************************/

#ifndef INCLUDE_NLOHMANN_JSON_HPP_
#define INCLUDE_NLOHMANN_JSON_HPP_

#include <algorithm> // all_of, find, for_each
#include <cstddef> // nullptr_t, ptrdiff_t, size_t
#include <functional> // hash, less
#include <initializer_list> // initializer_list
#ifndef JSON_NO_IO
    #include <iosfwd> // istream, ostream
#endif  // JSON_NO_IO
#include <iterator> // random_access_iterator_tag
#include <memory> // unique_ptr
#include <string> // string, stoi, to_string
#include <utility> // declval, forward, move, pair, swap
#include <vector> // vector

#include <nlohmann/adl_serializer.hpp>
#include <nlohmann/byte_container_with_subtype.hpp>
#include <nlohmann/detail/conversions/from_json.hpp>
#include <nlohmann/detail/conversions/to_json.hpp>
#include <nlohmann/detail/exceptions.hpp>
#include <nlohmann/detail/hash.hpp>
#include <nlohmann/detail/input/binary_reader.hpp>
#include <nlohmann/detail/input/input_adapters.hpp>
#include <nlohmann/detail/input/lexer.hpp>
#include <nlohmann/detail/input/parser.hpp>
#include <nlohmann/detail/iterators/internal_iterator.hpp>
#include <nlohmann/detail/iterators/iter_impl.hpp>
#include <nlohmann/detail/iterators/iteration_proxy.hpp>
#include <nlohmann/detail/iterators/json_reverse_iterator.hpp>
#include <nlohmann/detail/iterators/primitive_iterator.hpp>
#include <nlohmann/detail/json_custom_base_class.hpp>
#include <nlohmann/detail/json_pointer.hpp>
#include <nlohmann/detail/json_ref.hpp>
#include <nlohmann/detail/macro_scope.hpp>
#include <nlohmann/detail/string_concat.hpp>
#include <nlohmann/detail/string_escape.hpp>
#include <nlohmann/detail/string_utils.hpp>
#include <nlohmann/detail/meta/cpp_future.hpp>
#include <nlohmann/detail/meta/type_traits.hpp>
#include <nlohmann/detail/output/binary_writer.hpp>
#include <nlohmann/detail/output/output_adapters.hpp>
#include <nlohmann/detail/output/serializer.hpp>
#include <nlohmann/detail/value_t.hpp>
#include <nlohmann/json_fwd.hpp>
#include <nlohmann/ordered_map.hpp>

#if defined(JSON_HAS_CPP_17)
    #if JSON_HAS_STATIC_RTTI
        #include <any>
    #endif
    #include <string_view>
#endif

/*!
@brief namespace for Niels Lohmann
@see https://github.com/nlohmann
@since version 1.0.0
*/
NLOHMANN_JSON_NAMESPACE_BEGIN

/*!
@brief a class to store JSON values

@internal
@invariant The member variables @a m_value and @a m_type have the following
relationship:
- If `m_type == value_t::object`, then `m_value.object != nullptr`.
- If `m_type == value_t::array`, then `m_value.array != nullptr`.
- If `m_type == value_t::string`, then `m_value.string != nullptr`.
The invariants are checked by member function assert_invariant().

@note ObjectType trick from https://stackoverflow.com/a/9860911
@endinternal

@since version 1.0.0

@nosubgrouping
*/
NLOHMANN_BASIC_JSON_TPL_DECLARATION
class basic_json // NOLINT(cppcoreguidelines-special-member-functions,hicpp-special-member-functions)
    : public ::nlohmann::detail::json_base_class<CustomBaseClass>
{
  private:
    template<detail::value_t> friend struct detail::external_constructor;

    template<typename>
    friend class ::nlohmann::json_pointer;
    // can be restored when json_pointer backwards compatibility is removed
    // friend ::nlohmann::json_pointer<StringType>;

    template<typename BasicJsonType, typename InputType>
    friend class ::nlohmann::detail::parser;
    friend ::nlohmann::detail::serializer<basic_json>;
    template<typename BasicJsonType>
    friend class ::nlohmann::detail::iter_impl;
    template<typename BasicJsonType, typename CharType>
    friend class ::nlohmann::detail::binary_writer;
    template<typename BasicJsonType, typename InputType, typename SAX>
    friend class ::nlohmann::detail::binary_reader;
    template<typename BasicJsonType, typename InputAdapterType>
    friend class ::nlohmann::detail::json_sax_dom_parser;
    template<typename BasicJsonType, typename InputAdapterType>
    friend class ::nlohmann::detail::json_sax_dom_callback_parser;
    friend class ::nlohmann::detail::exception;

    /// workaround type for MSVC
    using basic_json_t = NLOHMANN_BASIC_JSON_TPL;
    using json_base_class_t = ::nlohmann::detail::json_base_class<CustomBaseClass>;

  JSON_PRIVATE_UNLESS_TESTED:
    // convenience aliases for types residing in namespace detail;
    using lexer = ::nlohmann::detail::lexer_base<basic_json>;

    template<typename InputAdapterType>
    static ::nlohmann::detail::parser<basic_json, InputAdapterType> parser(
        InputAdapterType adapter,
        detail::parser_callback_t<basic_json>cb = nullptr,
        const bool allow_exceptions = true,
        const bool ignore_comments = false,
        const bool ignore_trailing_commas = false
    )
    {
        return ::nlohmann::detail::parser<basic_json, InputAdapterType>(std::move(adapter),
               std::move(cb), allow_exceptions, ignore_comments, ignore_trailing_commas);
    }

  private:
    using primitive_iterator_t = ::nlohmann::detail::primitive_iterator_t;
    template<typename BasicJsonType>
    using internal_iterator = ::nlohmann::detail::internal_iterator<BasicJsonType>;
    template<typename BasicJsonType>
    using iter_impl = ::nlohmann::detail::iter_impl<BasicJsonType>;
    template<typename Iterator>
    using iteration_proxy = ::nlohmann::detail::iteration_proxy<Iterator>;
    template<typename Base> using json_reverse_iterator = ::nlohmann::detail::json_reverse_iterator<Base>;

    template<typename CharType>
    using output_adapter_t = ::nlohmann::detail::output_adapter_t<CharType>;

    template<typename InputType>
    using binary_reader = ::nlohmann::detail::binary_reader<basic_json, InputType>;
    template<typename CharType> using binary_writer = ::nlohmann::detail::binary_writer<basic_json, CharType>;

  JSON_PRIVATE_UNLESS_TESTED:
    using serializer = ::nlohmann::detail::serializer<basic_json>;

  public:
    using value_t = detail::value_t;
    /// JSON Pointer, see @ref nlohmann::json_pointer
    using json_pointer = ::nlohmann::json_pointer<StringType>;
    template<typename T, typename SFINAE>
    using json_serializer = JSONSerializer<T, SFINAE>;
    /// how to treat decoding errors
    using error_handler_t = detail::error_handler_t;
    /// how to treat CBOR tags
    using cbor_tag_handler_t = detail::cbor_tag_handler_t;
    /// how to encode BJData
    using bjdata_version_t = detail::bjdata_version_t;
    /// helper type for initializer lists of basic_json values
    using initializer_list_t = std::initializer_list<detail::json_ref<basic_json>>;

    using input_format_t = detail::input_format_t;
    /// SAX interface type, see @ref nlohmann::json_sax
    using json_sax_t = json_sax<basic_json>;

    ////////////////
    // exceptions //
    ////////////////

    /// @name exceptions
    /// Classes to implement user-defined exceptions.
    /// @{

    using exception = detail::exception;
    using parse_error = detail::parse_error;
    using invalid_iterator = detail::invalid_iterator;
    using type_error = detail::type_error;
    using out_of_range = detail::out_of_range;
    using other_error = detail::other_error;

    /// @}

