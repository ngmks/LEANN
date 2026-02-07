/*
 * Scala (https://www.scala-lang.org)
 *
 * Copyright EPFL and Lightbend, Inc. dba Akka
 *
 * Licensed under Apache License 2.0
 * (http://www.apache.org/licenses/LICENSE-2.0).
 *
 * See the NOTICE file distributed with this work for
 * additional information regarding copyright ownership.
 */

package scala

object Option {

  import scala.language.implicitConversions

  /** An implicit conversion that converts an option to an iterable value. */
  implicit def option2Iterable[A](xo: Option[A]): Iterable[A] =
    if (xo.isEmpty) Iterable.empty else Iterable.single(xo.get)

  /** An `Option` factory which creates `Some(x)` if the argument is not `null`,
   *  and `None` if it is `null`.
   *
   *  @param  x the value
   *  @return   `Some(value)` if value != null, `None` if value == null
   */
  def apply[A](x: A): Option[A] = if (x == null) None else Some(x)

  /** An Option factory which returns `None` in a manner consistent with
   *  the collections hierarchy.
   */
  def empty[A] : Option[A] = None

  /** When a given condition is true, evaluates the `a` argument and returns
   *  `Some(a)`. When the condition is false, `a` is not evaluated and `None` is
   *  returned.
   */
  def when[A](cond: Boolean)(a: => A): Option[A] =
    if (cond) Some(a) else None

  /** Unless a given condition is true, this will evaluate the `a` argument and
   *  return `Some(a)`. Otherwise, `a` is not evaluated and `None` is returned.
   */
  @inline def unless[A](cond: Boolean)(a: => A): Option[A] =
    when(!cond)(a)
}

/** Represents optional values. Instances of `Option`
 *  are either an instance of $some or the object $none.
 *
 *  The most idiomatic way to use an $option instance is to treat it
 *  as a collection or monad and use `map`,`flatMap`, `filter`, or
 *  `foreach`:
 *
 *  {{{
 *  val name: Option[String] = request.getParameter("name")
 *  val upper = name.map(_.trim).filter(_.length != 0).map(_.toUpperCase)
 *  println(upper.getOrElse(""))
 *  }}}
 *
 *  Note that this is equivalent to {{{
 *  val upper = for {
 *    name <- request.getParameter("name")
 *    trimmed <- Some(name.trim)
 *    upper <- Some(trimmed.toUpperCase) if trimmed.length != 0
 *  } yield upper
 *  println(upper.getOrElse(""))
 *  }}}
 *
 *  Because of how for comprehension works, if $none is returned
 *  from `request.getParameter`, the entire expression results in
 *  $none
 *
 *  This allows for sophisticated chaining of $option values without
 *  having to check for the existence of a value.
 *
 * These are useful methods that exist for both $some and $none.
 *  - [[isDefined]] — True if not empty
 *  - [[isEmpty]] — True if empty
 *  - [[nonEmpty]] — True if not empty
 *  - [[orElse]] — Evaluate and return alternate optional value if empty
 *  - [[getOrElse]] — Evaluate and return alternate value if empty
 *  - [[get]] — Return value, throw exception if empty
 *  - [[fold]] —  Apply function on optional value, return default if empty
 *  - [[map]] — Apply a function on the optional value
 *  - [[flatMap]] — Same as map but function must return an optional value
 *  - [[foreach]] — Apply a procedure on option value
 *  - [[collect]] — Apply partial pattern match on optional value
 *  - [[filter]] — An optional value satisfies predicate
 *  - [[filterNot]] — An optional value doesn't satisfy predicate
 *  - [[exists]] — Apply predicate on optional value, or `false` if empty
 *  - [[forall]] — Apply predicate on optional value, or `true` if empty
 *  - [[contains]] — Checks if value equals optional value, or `false` if empty
 *  - [[zip]] — Combine two optional values to make a paired optional value
 *  - [[unzip]] — Split an optional pair to two optional values
 *  - [[unzip3]] — Split an optional triple to three optional values
 *  - [[toList]] — Unary list of optional value, otherwise the empty list
 *
 *  A less-idiomatic way to use $option values is via pattern matching: {{{
 *  val nameMaybe = request.getParameter("name")
 *  nameMaybe match {
 *    case Some(name) =>
 *      println(name.trim.toUppercase)
 *    case None =>
 *      println("No name value")
 *  }
 *  }}}
 *
 * Interacting with code that can occasionally return `null` can be
 * safely wrapped in $option to become $none and $some otherwise. {{{
 * val abc = new java.util.HashMap[Int, String]
 * abc.put(1, "A")
 * bMaybe = Option(abc.get(2))
 * bMaybe match {
 *   case Some(b) =>
 *     println(s"Found \$b")
 *   case None =>
 *     println("Not found")
 * }
 * }}}
 *
 *  @note Many of the methods in here are duplicative with those
 *  in the `Iterable` hierarchy, but they are duplicated for a reason:
 *  the implicit conversion tends to leave one with an `Iterable` in
 *  situations where one could have retained an `Option`.
 *
 *  @define none `None`
 *  @define some [[scala.Some]]
 *  @define option [[scala.Option]]
 *  @define p `p`
 *  @define f `f`
 *  @define coll option
 *  @define Coll `Option`
 *  @define orderDependent
 *  @define orderDependentFold
 *  @define mayNotTerminateInf
 *  @define willNotTerminateInf
 *  @define collectExample
 *  @define undefinedorder
 */
@SerialVersionUID(-114498752079829388L) // value computed by serialver for 2.11.2, annotation added in 2.11.4
sealed abstract class Option[+A] extends IterableOnce[A] with Product with Serializable {
  self =>

  /** Returns `true` if the option is $none, `false` otherwise.
   *
   * This is equivalent to:
   * {{{
   * option match {
   *   case Some(_) => false
   *   case None    => true
   * }
   * }}}
   */
  final def isEmpty: Boolean = this eq None

  /** Returns `true` if the option is an instance of $some, `false` otherwise.
   *
   * This is equivalent to:
   * {{{
   * option match {
   *   case Some(_) => true
   *   case None    => false
   * }
   * }}}
   */
  final def isDefined: Boolean = !isEmpty

  override final def knownSize: Int = if (isEmpty) 0 else 1

  /** Returns the option's value.
   *
   * This is equivalent to:
   * {{{
   * option match {
   *   case Some(x) => x
   *   case None    => throw new Exception
   * }
   * }}}
   *  @note The option must be nonempty.
   *  @throws NoSuchElementException if the option is empty.
   */
  def get: A

  /** Returns the option's value if the option is nonempty, otherwise
   * return the result of evaluating `default`.
   *
   * This is equivalent to:
   * {{{
   * option match {
   *   case Some(x) => x
   *   case None    => default
   * }
   * }}}
   *
   *  @param default  the default expression.
   */
  @inline final def getOrElse[B >: A](default: => B): B =
