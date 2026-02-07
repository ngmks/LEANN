#' Create, modify, and delete columns
#'
#' `mutate()` creates new columns that are functions of existing variables.
#' It can also modify (if the name is the same as an existing
#' column) and delete columns (by setting their value to `NULL`).
#'
#' @section Useful mutate functions:
#'
#' * [`+`], [`-`], [log()], etc., for their usual mathematical meanings
#'
#' * [lead()], [lag()]
#'
#' * [dense_rank()], [min_rank()], [percent_rank()], [row_number()],
#'   [cume_dist()], [ntile()]
#'
#' * [cumsum()], [cummean()], [cummin()], [cummax()], [cumany()], [cumall()]
#'
#' * [na_if()], [coalesce()]
#'
#' * [if_else()], [recode()], [case_when()]
#'
#' @section Grouped tibbles:
#'
#' Because mutating expressions are computed within groups, they may
#' yield different results on grouped tibbles. This will be the case
#' as soon as an aggregating, lagging, or ranking function is
#' involved. Compare this ungrouped mutate:
#'
#' ```
#' starwars |>
#'   select(name, mass, species) |>
#'   mutate(mass_norm = mass / mean(mass, na.rm = TRUE))
#' ```
#'
#' With the grouped equivalent:
#'
#' ```
#' starwars |>
#'   select(name, mass, species) |>
#'   group_by(species) |>
#'   mutate(mass_norm = mass / mean(mass, na.rm = TRUE))
#' ```
#'
#' The former normalises `mass` by the global average whereas the
#' latter normalises by the averages within species levels.
#'
#' @export
#' @inheritParams arrange
#' @param ... <[`data-masking`][rlang::args_data_masking]> Name-value pairs.
#'   The name gives the name of the column in the output.
#'
#'   The value can be:
#'
#'   * A vector of length 1, which will be recycled to the correct length.
#'   * A vector the same length as the current group (or the whole data frame
#'     if ungrouped).
#'   * `NULL`, to remove the column.
#'   * A data frame or tibble, to create multiple columns in the output.
#' @family single table verbs
#' @return
#' An object of the same type as `.data`. The output has the following
#' properties:
#'
#' * Columns from `.data` will be preserved according to the `.keep` argument.
#' * Existing columns that are modified by `...` will always be returned in
#'   their original location.
#' * New columns created through `...` will be placed according to the
#'   `.before` and `.after` arguments.
#' * The number of rows is not affected.
#' * Columns given the value `NULL` will be removed.
#' * Groups will be recomputed if a grouping variable is mutated.
#' * Data frame attributes are preserved.
#' @section Methods:
#' This function is a **generic**, which means that packages can provide
#' implementations (methods) for other classes. See the documentation of
#' individual methods for extra arguments and differences in behaviour.
#'
#' Methods available in currently loaded packages:
#' \Sexpr[stage=render,results=rd]{dplyr:::methods_rd("mutate")}.
#' @examples
#' # Newly created variables are available immediately
#' starwars |>
#'   select(name, mass) |>
#'   mutate(
#'     mass2 = mass * 2,
#'     mass2_squared = mass2 * mass2
#'   )
#'
#' # As well as adding new variables, you can use mutate() to
#' # remove variables and modify existing variables.
#' starwars |>
#'   select(name, height, mass, homeworld) |>
#'   mutate(
#'     mass = NULL,
#'     height = height * 0.0328084 # convert to feet
#'   )
#'
#' # Use across() with mutate() to apply a transformation
#' # to multiple columns in a tibble.
#' starwars |>
#'   select(name, homeworld, species) |>
#'   mutate(across(!name, as.factor))
#' # see more in ?across
#'
#' # Window functions are useful for grouped mutates:
#' starwars |>
#'   select(name, mass, homeworld) |>
#'   group_by(homeworld) |>
#'   mutate(rank = min_rank(desc(mass)))
#' # see `vignette("window-functions")` for more details
#'
#' # By default, new columns are placed on the far right.
#' df <- tibble(x = 1, y = 2)
#' df |> mutate(z = x + y)
#' df |> mutate(z = x + y, .before = 1)
#' df |> mutate(z = x + y, .after = x)
#'
#' # By default, mutate() keeps all columns from the input data.
#' df <- tibble(x = 1, y = 2, a = "a", b = "b")
#' df |> mutate(z = x + y, .keep = "all") # the default
#' df |> mutate(z = x + y, .keep = "used")
#' df |> mutate(z = x + y, .keep = "unused")
#' df |> mutate(z = x + y, .keep = "none")
#'
#' # Grouping ----------------------------------------
#' # The mutate operation may yield different results on grouped
#' # tibbles because the expressions are computed within groups.
#' # The following normalises `mass` by the global average:
#' starwars |>
#'   select(name, mass, species) |>
#'   mutate(mass_norm = mass / mean(mass, na.rm = TRUE))
#'
#' # Whereas this normalises `mass` by the averages within species
#' # levels:
#' starwars |>
#'   select(name, mass, species) |>
#'   group_by(species) |>
#'   mutate(mass_norm = mass / mean(mass, na.rm = TRUE))
#'
#' # Indirection ----------------------------------------
#' # Refer to column names stored as strings with the `.data` pronoun:
#' vars <- c("mass", "height")
#' mutate(starwars, prod = .data[[vars[[1]]]] * .data[[vars[[2]]]])
#' # Learn more in ?rlang::args_data_masking
mutate <- function(.data, ...) {
  UseMethod("mutate")
}

#' @rdname mutate
#'
#' @inheritParams args_by
#'
#' @param .keep
#'   Control which columns from `.data` are retained in the output. Grouping
#'   columns and columns created by `...` are always kept.
#'
#'   * `"all"` retains all columns from `.data`. This is the default.
#'   * `"used"` retains only the columns used in `...` to create new
#'     columns. This is useful for checking your work, as it displays inputs
#'     and outputs side-by-side.
#'   * `"unused"` retains only the columns _not_ used in `...` to create new
#'     columns. This is useful if you generate new columns, but no longer need
#'     the columns used to generate them.
#'   * `"none"` doesn't retain any extra columns from `.data`. Only the grouping
#'     variables and columns created by `...` are kept.
#' @param .before,.after
#'   <[`tidy-select`][dplyr_tidy_select]> Optionally, control where new columns
#'   should appear (the default is to add to the right hand side). See
#'   [relocate()] for more details.
#' @export
mutate.data.frame <- function(
  .data,
  ...,
  .by = NULL,
  .keep = c("all", "used", "unused", "none"),
  .before = NULL,
  .after = NULL
) {
  keep <- arg_match0(.keep, values = c("all", "used", "unused", "none"))

  by <- compute_by({{ .by }}, .data, by_arg = ".by", data_arg = ".data")

  cols <- mutate_cols(.data, dplyr_quosures(...), by)
  used <- attr(cols, "used")

  out <- dplyr_col_modify(.data, cols)

  names_original <- names(.data)

  out <- mutate_relocate(
    out = out,
    before = {{ .before }},
    after = {{ .after }},
    names_original = names_original
  )

  names_new <- names(cols)
  names_groups <- by$names

  out <- mutate_keep(
