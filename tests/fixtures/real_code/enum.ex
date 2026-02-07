# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 The Elixir Team
# SPDX-FileCopyrightText: 2012 Plataformatec

defprotocol Enumerable do
  @moduledoc """
  Enumerable protocol used by `Enum` and `Stream` modules.

  When you invoke a function in the `Enum` module, the first argument
  is usually a collection that must implement this protocol.
  For example, the expression `Enum.map([1, 2, 3], &(&1 * 2))`
  invokes `Enumerable.reduce/3` to perform the reducing operation that
  builds a mapped list by calling the mapping function `&(&1 * 2)` on
  every element in the collection and consuming the element with an
  accumulated list.

  Internally, `Enum.map/2` is implemented as follows:

      def map(enumerable, fun) do
        reducer = fn x, acc -> {:cont, [fun.(x) | acc]} end
        Enumerable.reduce(enumerable, {:cont, []}, reducer) |> elem(1) |> :lists.reverse()
      end

  Note that the user-supplied function is wrapped into a `t:reducer/0` function.
  The `t:reducer/0` function must return a tagged tuple after each step,
  as described in the `t:acc/0` type. At the end, `Enumerable.reduce/3`
  returns `t:result/0`.

  This protocol uses tagged tuples to exchange information between the
  reducer function and the data type that implements the protocol. This
  allows enumeration of resources, such as files, to be done efficiently
  while also guaranteeing the resource will be closed at the end of the
  enumeration. This protocol also allows suspension of the enumeration,
  which is useful when interleaving between many enumerables is required
  (as in the `zip/1` and `zip/2` functions).

  This protocol requires four functions to be implemented, `reduce/3`,
  `count/1`, `member?/2`, and `slice/1`. The core of the protocol is the
  `reduce/3` function. All other functions exist as optimizations paths
  for data structures that can implement certain properties in better
  than linear time.

  ## Default implementation for lists

  Sometimes you may want to implement this protocol for a list contained
  in struct. This can be done by delegating to the `Enumerable.List` module
  in the `reduce/3` implementation and providing a straight-forward
  implementation for the remaining ones:

      defimpl Enumerable, for: CustomStruct do
        def count(struct), do: {:ok, length(struct.items)}
        def member?(struct, value), do: {:ok, value in struct.items}
        def slice(struct), do: {:error, __MODULE__}
        def reduce(struct, acc, fun), do: Enumerable.List.reduce(struct.items, acc, fun)
      end
  """

  @typedoc """
  An enumerable of elements of type `element`.

  This type is equivalent to `t:t/0` but is especially useful for documentation.

  For example, imagine you define a function that expects an enumerable of
  integers and returns an enumerable of strings:

      @spec integers_to_strings(Enumerable.t(integer())) :: Enumerable.t(String.t())
      def integers_to_strings(integers) do
        Stream.map(integers, &Integer.to_string/1)
      end

  """
  @typedoc since: "1.14.0"
  @type t(_element) :: t()

  @typedoc """
  The accumulator value for each step.

  It must be a tagged tuple with one of the following "tags":

    * `:cont`    - the enumeration should continue
    * `:halt`    - the enumeration should halt immediately
    * `:suspend` - the enumeration should be suspended immediately

  Depending on the accumulator value, the result returned by
  `Enumerable.reduce/3` will change. Please check the `t:result/0`
  type documentation for more information.

  In case a `t:reducer/0` function returns a `:suspend` accumulator,
  it must be explicitly handled by the caller and never leak.
  """
  @type acc :: {:cont, term} | {:halt, term} | {:suspend, term}

  @typedoc """
  The reducer function.

  Should be called with the `enumerable` element and the
  accumulator contents.

  Returns the accumulator for the next enumeration step.
  """
  @type reducer :: (element :: term, element_acc :: term -> acc)

  @typedoc """
  The result of the reduce operation.

  It may be *done* when the enumeration is finished by reaching
  its end, or *halted*/*suspended* when the enumeration was halted
  or suspended by the tagged accumulator.

  In case the tagged `:halt` accumulator is given, the `:halted` tuple
  with the accumulator must be returned. Functions like `Enum.take_while/2`
  use `:halt` underneath and can be used to test halting enumerables.

  In case the tagged `:suspend` accumulator is given, the caller must
  return the `:suspended` tuple with the accumulator and a continuation.
  The caller is then responsible of managing the continuation and the
  caller must always call the continuation, eventually halting or continuing
  until the end. `Enum.zip/2` uses suspension, so it can be used to test
  whether your implementation handles suspension correctly. You can also use
  `Stream.zip/2` with `Enum.take_while/2` to test the combination of
  `:suspend` with `:halt`.
  """
  @type result ::
          {:done, term}
          | {:halted, term}
          | {:suspended, term, continuation}

  @typedoc """
  A partially applied reduce function.

  The continuation is the closure returned as a result when
  the enumeration is suspended. When invoked, it expects
  a new accumulator and it returns the result.

  A continuation can be trivially implemented as long as the reduce
  function is defined in a tail recursive fashion. If the function
  is tail recursive, all the state is passed as arguments, so
  the continuation is the reducing function partially applied.
  """
  @type continuation :: (acc -> result)

  @typedoc """
  A slicing function that receives the initial position,
  the number of elements in the slice, and the step.

  The `start` position is a number `>= 0` and guaranteed to
  exist in the `enumerable`. The length is a number `>= 1`
  in a way that `start + length * step <= count`, where
  `count` is the maximum amount of elements in the enumerable.

  The function should return a non empty list where
  the amount of elements is equal to `length`.
  """
  @type slicing_fun ::
          (start :: non_neg_integer, length :: pos_integer, step :: pos_integer -> [term()])

  @typedoc """
  Receives an enumerable and returns a list.
  """
  @type to_list_fun :: (t -> [term()])

  @doc """
  Reduces the `enumerable` into an element.

  Most of the operations in `Enum` are implemented in terms of reduce.
  This function should apply the given `t:reducer/0` function to each
  element in the `enumerable` and proceed as expected by the returned
  accumulator.

  See the documentation of the types `t:result/0` and `t:acc/0` for
  more information.

  ## Examples

  As an example, here is the implementation of `reduce` for lists:

      def reduce(_list, {:halt, acc}, _fun), do: {:halted, acc}
      def reduce(list, {:suspend, acc}, fun), do: {:suspended, acc, &reduce(list, &1, fun)}
      def reduce([], {:cont, acc}, _fun), do: {:done, acc}
      def reduce([head | tail], {:cont, acc}, fun), do: reduce(tail, fun.(head, acc), fun)

  """
  @spec reduce(t, acc, reducer) :: result
  def reduce(enumerable, acc, fun)

  @doc """
  Retrieves the number of elements in the `enumerable`.

  It should return `{:ok, count}` if you can count the number of elements
  in `enumerable` in a faster way than fully traversing it.

  Otherwise it should return `{:error, __MODULE__}` and a default algorithm
  built on top of `reduce/3` that runs in linear time will be used.
  """
  @spec count(t) :: {:ok, non_neg_integer} | {:error, module}
  def count(enumerable)

  @doc """
  Checks if an `element` exists within the `enumerable`.

