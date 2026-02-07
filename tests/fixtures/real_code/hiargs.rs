/*!
Provides the definition of high level arguments from CLI flags.
*/

use std::{
    collections::HashSet,
    path::{Path, PathBuf},
};

use {
    bstr::BString,
    grep::printer::{ColorSpecs, SummaryKind},
};

use crate::{
    flags::lowargs::{
        BinaryMode, BoundaryMode, BufferMode, CaseMode, ColorChoice,
        ContextMode, ContextSeparator, EncodingMode, EngineChoice,
        FieldContextSeparator, FieldMatchSeparator, LowArgs, MmapMode, Mode,
        PatternSource, SearchMode, SortMode, SortModeKind, TypeChange,
    },
    haystack::{Haystack, HaystackBuilder},
    search::{PatternMatcher, Printer, SearchWorker, SearchWorkerBuilder},
};

/// A high level representation of CLI arguments.
///
/// The distinction between low and high level arguments is somewhat arbitrary
/// and wishy washy. The main idea here is that high level arguments generally
/// require all of CLI parsing to be finished. For example, one cannot
/// construct a glob matcher until all of the glob patterns are known.
///
/// So while low level arguments are collected during parsing itself, high
/// level arguments aren't created until parsing has completely finished.
#[derive(Debug)]
pub(crate) struct HiArgs {
    binary: BinaryDetection,
    boundary: Option<BoundaryMode>,
    buffer: BufferMode,
    byte_offset: bool,
    case: CaseMode,
    color: ColorChoice,
    colors: grep::printer::ColorSpecs,
    column: bool,
    context: ContextMode,
    context_separator: ContextSeparator,
    crlf: bool,
    cwd: PathBuf,
    dfa_size_limit: Option<usize>,
    encoding: EncodingMode,
    engine: EngineChoice,
    field_context_separator: FieldContextSeparator,
    field_match_separator: FieldMatchSeparator,
    file_separator: Option<Vec<u8>>,
    fixed_strings: bool,
    follow: bool,
    globs: ignore::overrides::Override,
    heading: bool,
    hidden: bool,
    hyperlink_config: grep::printer::HyperlinkConfig,
    ignore_file_case_insensitive: bool,
    ignore_file: Vec<PathBuf>,
    include_zero: bool,
    invert_match: bool,
    is_terminal_stdout: bool,
    line_number: bool,
    max_columns: Option<u64>,
    max_columns_preview: bool,
    max_count: Option<u64>,
    max_depth: Option<usize>,
    max_filesize: Option<u64>,
    mmap_choice: grep::searcher::MmapChoice,
    mode: Mode,
    multiline: bool,
    multiline_dotall: bool,
    no_ignore_dot: bool,
    no_ignore_exclude: bool,
    no_ignore_files: bool,
    no_ignore_global: bool,
    no_ignore_parent: bool,
    no_ignore_vcs: bool,
    no_require_git: bool,
    no_unicode: bool,
    null_data: bool,
    one_file_system: bool,
    only_matching: bool,
    path_separator: Option<u8>,
    paths: Paths,
    path_terminator: Option<u8>,
    patterns: Patterns,
    pre: Option<PathBuf>,
    pre_globs: ignore::overrides::Override,
    quiet: bool,
    quit_after_match: bool,
    regex_size_limit: Option<usize>,
    replace: Option<BString>,
    search_zip: bool,
    sort: Option<SortMode>,
    stats: Option<grep::printer::Stats>,
    stop_on_nonmatch: bool,
    threads: usize,
    trim: bool,
    types: ignore::types::Types,
    vimgrep: bool,
    with_filename: bool,
}

impl HiArgs {
    /// Convert low level arguments into high level arguments.
    ///
    /// This process can fail for a variety of reasons. For example, invalid
    /// globs or some kind of environment issue.
    pub(crate) fn from_low_args(mut low: LowArgs) -> anyhow::Result<HiArgs> {
        // Callers should not be trying to convert low-level arguments when
        // a short-circuiting special mode is present.
        assert_eq!(None, low.special, "special mode demands short-circuiting");
        // If the sorting mode isn't supported, then we bail loudly. I'm not
        // sure if this is the right thing to do. We could silently "not sort"
        // as well. If we wanted to go that route, then we could just set
        // `low.sort = None` if `supported()` returns an error.
        if let Some(ref sort) = low.sort {
            sort.supported()?;
        }

        // We modify the mode in-place on `low` so that subsequent conversions
        // see the correct mode.
        match low.mode {
            Mode::Search(ref mut mode) => match *mode {
                // treat `-v --count-matches` as `-v --count`
                SearchMode::CountMatches if low.invert_match => {
                    *mode = SearchMode::Count;
                }
                // treat `-o --count` as `--count-matches`
                SearchMode::Count if low.only_matching => {
                    *mode = SearchMode::CountMatches;
                }
                _ => {}
            },
            _ => {}
        }

        let mut state = State::new()?;
        let patterns = Patterns::from_low_args(&mut state, &mut low)?;
        let paths = Paths::from_low_args(&mut state, &patterns, &mut low)?;

        let binary = BinaryDetection::from_low_args(&state, &low);
        let colors = take_color_specs(&mut state, &mut low);
        let hyperlink_config = take_hyperlink_config(&mut state, &mut low)?;
        let stats = stats(&low);
        let types = types(&low)?;
        let globs = globs(&state, &low)?;
        let pre_globs = preprocessor_globs(&state, &low)?;

        let color = match low.color {
            ColorChoice::Auto if !state.is_terminal_stdout => {
                ColorChoice::Never
            }
            _ => low.color,
        };
        let column = low.column.unwrap_or(low.vimgrep);
        let heading = match low.heading {
            None => !low.vimgrep && state.is_terminal_stdout,
            Some(false) => false,
            Some(true) => !low.vimgrep,
        };
        let path_terminator = if low.null { Some(b'\x00') } else { None };
        let quit_after_match = stats.is_none() && low.quiet;
        let threads = if low.sort.is_some() || paths.is_one_file {
            1
        } else if let Some(threads) = low.threads {
            threads
        } else {
            std::thread::available_parallelism().map_or(1, |n| n.get()).min(12)
        };
        log::debug!("using {threads} thread(s)");
        let with_filename = low
            .with_filename
            .unwrap_or_else(|| low.vimgrep || !paths.is_one_file);

        let file_separator = match low.mode {
            Mode::Search(SearchMode::Standard) => {
                if heading {
                    Some(b"".to_vec())
                } else if let ContextMode::Limited(ref limited) = low.context {
                    let (before, after) = limited.get();
                    if before > 0 || after > 0 {
                        low.context_separator.clone().into_bytes()
                    } else {
                        None
                    }
                } else {
                    None
                }
            }
            _ => None,
        };

        let line_number = low.line_number.unwrap_or_else(|| {
            if low.quiet {
                return false;
            }
            let Mode::Search(ref search_mode) = low.mode else { return false };
            match *search_mode {
                SearchMode::FilesWithMatches
                | SearchMode::FilesWithoutMatch
                | SearchMode::Count
                | SearchMode::CountMatches => return false,
                SearchMode::JSON => return true,
                SearchMode::Standard => {
                    // A few things can imply counting line numbers. In
                    // particular, we generally want to show line numbers by
                    // default when printing to a tty for human consumption,
                    // except for one interesting case: when we're only
                    // searching stdin. This makes pipelines work as expected.
                    (state.is_terminal_stdout && !paths.is_only_stdin())
                        || column
                        || low.vimgrep
                }
            }
        });

        let mmap_choice = {
            // SAFETY: Memory maps are difficult to impossible to encapsulate
            // safely in a portable way that doesn't simultaneously negate some
            // of the benfits of using memory maps. For ripgrep's use, we never
            // mutate a memory map and generally never store the contents of
            // memory map in a data structure that depends on immutability.
            // Generally speaking, the worst thing that can happen is a SIGBUS
            // (if the underlying file is truncated while reading it), which
            // will cause ripgrep to abort. This reasoning should be treated as
            // suspect.
            let maybe = unsafe { grep::searcher::MmapChoice::auto() };
            let never = grep::searcher::MmapChoice::never();
            match low.mmap {
                MmapMode::Auto => {
                    if paths.paths.len() <= 10
                        && paths.paths.iter().all(|p| p.is_file())
                    {
                        // If we're only searching a few paths and all of them
                        // are files, then memory maps are probably faster.
                        maybe
                    } else {
                        never
                    }
                }
                MmapMode::AlwaysTryMmap => maybe,
                MmapMode::Never => never,
            }
        };

        Ok(HiArgs {
            mode: low.mode,
            patterns,
            paths,
            binary,
            boundary: low.boundary,
            buffer: low.buffer,
            byte_offset: low.byte_offset,
            case: low.case,
            color,
            colors,
            column,
            context: low.context,
            context_separator: low.context_separator,
            crlf: low.crlf,
            cwd: state.cwd,
            dfa_size_limit: low.dfa_size_limit,
            encoding: low.encoding,
            engine: low.engine,
            field_context_separator: low.field_context_separator,
            field_match_separator: low.field_match_separator,
            file_separator,
            fixed_strings: low.fixed_strings,
            follow: low.follow,
            heading,
            hidden: low.hidden,
            hyperlink_config,
            ignore_file: low.ignore_file,
            ignore_file_case_insensitive: low.ignore_file_case_insensitive,
            include_zero: low.include_zero,
            invert_match: low.invert_match,
            is_terminal_stdout: state.is_terminal_stdout,
            line_number,
            max_columns: low.max_columns,
            max_columns_preview: low.max_columns_preview,
            max_count: low.max_count,
            max_depth: low.max_depth,
            max_filesize: low.max_filesize,
            mmap_choice,
            multiline: low.multiline,
            multiline_dotall: low.multiline_dotall,
            no_ignore_dot: low.no_ignore_dot,
            no_ignore_exclude: low.no_ignore_exclude,
            no_ignore_files: low.no_ignore_files,
            no_ignore_global: low.no_ignore_global,
            no_ignore_parent: low.no_ignore_parent,
            no_ignore_vcs: low.no_ignore_vcs,
            no_require_git: low.no_require_git,
            no_unicode: low.no_unicode,
            null_data: low.null_data,
