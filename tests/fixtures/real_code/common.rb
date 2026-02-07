# frozen_string_literal: true
#--
# = uri/common.rb
#
# Author:: Akira Yamada <akira@ruby-lang.org>
# License::
#   You can redistribute it and/or modify it under the same term as Ruby.
#
# See URI for general documentation
#

require_relative "rfc2396_parser"
require_relative "rfc3986_parser"

module URI
  # The default parser instance for RFC 2396.
  RFC2396_PARSER = RFC2396_Parser.new
  Ractor.make_shareable(RFC2396_PARSER) if defined?(Ractor)

  # The default parser instance for RFC 3986.
  RFC3986_PARSER = RFC3986_Parser.new
  Ractor.make_shareable(RFC3986_PARSER) if defined?(Ractor)

  # The default parser instance.
  DEFAULT_PARSER = RFC3986_PARSER
  Ractor.make_shareable(DEFAULT_PARSER) if defined?(Ractor)

  # Set the default parser instance.
  def self.parser=(parser = RFC3986_PARSER)
    remove_const(:Parser) if defined?(::URI::Parser)
    const_set("Parser", parser.class)

    remove_const(:PARSER) if defined?(::URI::PARSER)
    const_set("PARSER", parser)

    remove_const(:REGEXP) if defined?(::URI::REGEXP)
    remove_const(:PATTERN) if defined?(::URI::PATTERN)
    if Parser == RFC2396_Parser
      const_set("REGEXP", URI::RFC2396_REGEXP)
      const_set("PATTERN", URI::RFC2396_REGEXP::PATTERN)
    end

    Parser.new.regexp.each_pair do |sym, str|
      remove_const(sym) if const_defined?(sym, false)
      const_set(sym, str)
    end
  end
  self.parser = RFC3986_PARSER

  def self.const_missing(const) # :nodoc:
    if const == :REGEXP
      warn "URI::REGEXP is obsolete. Use URI::RFC2396_REGEXP explicitly.", uplevel: 1 if $VERBOSE
      URI::RFC2396_REGEXP
    elsif value = RFC2396_PARSER.regexp[const]
      warn "URI::#{const} is obsolete. Use URI::RFC2396_PARSER.regexp[#{const.inspect}] explicitly.", uplevel: 1 if $VERBOSE
      value
    elsif value = RFC2396_Parser.const_get(const)
      warn "URI::#{const} is obsolete. Use URI::RFC2396_Parser::#{const} explicitly.", uplevel: 1 if $VERBOSE
      value
    else
      super
    end
  end

  module Util # :nodoc:
    def make_components_hash(klass, array_hash)
      tmp = {}
      if array_hash.kind_of?(Array) &&
          array_hash.size == klass.component.size - 1
        klass.component[1..-1].each_index do |i|
          begin
            tmp[klass.component[i + 1]] = array_hash[i].clone
          rescue TypeError
            tmp[klass.component[i + 1]] = array_hash[i]
          end
        end

      elsif array_hash.kind_of?(Hash)
        array_hash.each do |key, value|
          begin
            tmp[key] = value.clone
          rescue TypeError
            tmp[key] = value
          end
        end
      else
        raise ArgumentError,
          "expected Array of or Hash of components of #{klass} (#{klass.component[1..-1].join(', ')})"
      end
      tmp[:scheme] = klass.to_s.sub(/\A.*::/, '').downcase

      return tmp
    end
    module_function :make_components_hash
  end

  module Schemes # :nodoc:
    class << self
      ReservedChars = ".+-"
      EscapedChars = "\u01C0\u01C1\u01C2"
      # Use Lo category chars as escaped chars for TruffleRuby, which
      # does not allow Symbol categories as identifiers.

      def escape(name)
        unless name and name.ascii_only?
          return nil
        end
        name.upcase.tr(ReservedChars, EscapedChars)
      end

      def unescape(name)
        name.tr(EscapedChars, ReservedChars).encode(Encoding::US_ASCII).upcase
      end

      def find(name)
        const_get(name, false) if name and const_defined?(name, false)
      end

      def register(name, klass)
        unless scheme = escape(name)
          raise ArgumentError, "invalid character as scheme - #{name}"
        end
        const_set(scheme, klass)
      end

      def list
        constants.map { |name|
          [unescape(name.to_s), const_get(name)]
        }.to_h
      end
    end
  end
  private_constant :Schemes

  # Registers the given +klass+ as the class to be instantiated
  # when parsing a \URI with the given +scheme+:
  #
  #   URI.register_scheme('MS_SEARCH', URI::Generic) # => URI::Generic
  #   URI.scheme_list['MS_SEARCH']                   # => URI::Generic
  #
  # Note that after calling String#upcase on +scheme+, it must be a valid
  # constant name.
  def self.register_scheme(scheme, klass)
    Schemes.register(scheme, klass)
  end

  # Returns a hash of the defined schemes:
  #
  #   URI.scheme_list
  #   # =>
  #   {"MAILTO"=>URI::MailTo,
  #    "LDAPS"=>URI::LDAPS,
  #    "WS"=>URI::WS,
  #    "HTTP"=>URI::HTTP,
  #    "HTTPS"=>URI::HTTPS,
  #    "LDAP"=>URI::LDAP,
  #    "FILE"=>URI::File,
  #    "FTP"=>URI::FTP}
  #
  # Related: URI.register_scheme.
  def self.scheme_list
    Schemes.list
  end

  # :stopdoc:
  INITIAL_SCHEMES = scheme_list
  private_constant :INITIAL_SCHEMES
  Ractor.make_shareable(INITIAL_SCHEMES) if defined?(Ractor)
  # :startdoc:

  # Returns a new object constructed from the given +scheme+, +arguments+,
  # and +default+:
  #
  # - The new object is an instance of <tt>URI.scheme_list[scheme.upcase]</tt>.
  # - The object is initialized by calling the class initializer
  #   using +scheme+ and +arguments+.
  #   See URI::Generic.new.
  #
  # Examples:
  #
  #   values = ['john.doe', 'www.example.com', '123', nil, '/forum/questions/', nil, 'tag=networking&order=newest', 'top']
  #   URI.for('https', *values)
  #   # => #<URI::HTTPS https://john.doe@www.example.com:123/forum/questions/?tag=networking&order=newest#top>
  #   URI.for('foo', *values, default: URI::HTTP)
  #   # => #<URI::HTTP foo://john.doe@www.example.com:123/forum/questions/?tag=networking&order=newest#top>
  #
  def self.for(scheme, *arguments, default: Generic)
    const_name = Schemes.escape(scheme)

    uri_class = INITIAL_SCHEMES[const_name]
    uri_class ||= Schemes.find(const_name)
    uri_class ||= default

    return uri_class.new(scheme, *arguments)
  end

  #
  # Base class for all URI exceptions.
  #
  class Error < StandardError; end
