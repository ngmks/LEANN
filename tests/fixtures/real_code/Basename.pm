=head1 NAME

File::Basename - Parse file paths into directory, filename and suffix.

=head1 SYNOPSIS

    use File::Basename;

    my ($name, $path, $suffix) = fileparse($fullname, @suffixlist);
    my $name = fileparse($fullname, @suffixlist);

    my $basename = basename($fullname, @suffixlist);
    my $dirname  = dirname($fullname);


=head1 DESCRIPTION

These routines allow you to parse file paths into their directory, filename
and suffix.

B<NOTE>: C<dirname()> and C<basename()> emulate the behaviours, and
quirks, of the shell and C functions of the same name.  See each
function's documentation for details.  If your concern is just parsing
paths it is safer to use L<File::Spec>'s C<splitpath()> and
C<splitdir()> methods.

It is guaranteed that

    # Where $path_separator is / for Unix, \ for Windows, etc...
    dirname($path) . $path_separator . basename($path);

is equivalent to the original path for all systems but VMS.


=cut


package File::Basename;

# File::Basename is used during the Perl build, when the re extension may
# not be available, but we only actually need it if running under tainting.
BEGIN {
  if (${^TAINT}) {
    require re;
    re->import('taint');
  }
}


use strict;
use 5.006;
use warnings;
our(@ISA, @EXPORT, $VERSION, $Fileparse_fstype, $Fileparse_igncase);
require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(fileparse fileparse_set_fstype basename dirname);
$VERSION = "2.86";

fileparse_set_fstype($^O);


=over 4

=item C<fileparse>
X<fileparse>

    my($filename, $dirs, $suffix) = fileparse($path);
    my($filename, $dirs, $suffix) = fileparse($path, @suffixes);
    my $filename                  = fileparse($path, @suffixes);

The C<fileparse()> routine divides a file path into its $dirs, $filename
and (optionally) the filename $suffix.

$dirs contains everything up to and including the last
directory separator in the $path including the volume (if applicable).
The remainder of the $path is the $filename.

     # On Unix returns ("baz", "/foo/bar/", "")
     fileparse("/foo/bar/baz");

     # On Windows returns ("baz", 'C:\foo\bar\', "")
     fileparse('C:\foo\bar\baz');

     # On Unix returns ("", "/foo/bar/baz/", "")
     fileparse("/foo/bar/baz/");

If @suffixes are given each element is a pattern (either a string or a
C<qr//>) matched against the end of the $filename.  The matching
portion is removed and becomes the $suffix.

     # On Unix returns ("baz", "/foo/bar/", ".txt")
     fileparse("/foo/bar/baz.txt", qr/\.[^.]*/);

If type is non-Unix (see L</fileparse_set_fstype>) then the pattern
matching for suffix removal is performed case-insensitively, since
those systems are not case-sensitive when opening existing files.

You are guaranteed that C<$dirs . $filename . $suffix> will
denote the same location as the original $path.

=cut


sub fileparse {
  my($fullname,@suffices) = @_;

  unless (defined $fullname) {
      require Carp;
      Carp::croak("fileparse(): need a valid pathname");
  }

  my $orig_type = '';
  my($type,$igncase) = ($Fileparse_fstype, $Fileparse_igncase);

  my($taint) = substr($fullname,0,0);  # Is $fullname tainted?

  if ($type eq "VMS" and $fullname =~ m{/} ) {
    # We're doing Unix emulation
    $orig_type = $type;
    $type = 'Unix';
  }

  my($dirpath, $basename);

  if (grep { $type eq $_ } qw(MSDOS DOS MSWin32 Epoc)) {
    ($dirpath,$basename) = ($fullname =~ /^((?:.*[:\\\/])?)(.*)/s);
    $dirpath .= '.\\' unless $dirpath =~ /[\\\/]\z/;
  }
  elsif ($type eq "OS2") {
    ($dirpath,$basename) = ($fullname =~ m#^((?:.*[:\\/])?)(.*)#s);
    $dirpath = './' unless $dirpath;	# Can't be 0
    $dirpath .= '/' unless $dirpath =~ m#[\\/]\z#;
  }
  elsif ($type eq "MacOS") {
    ($dirpath,$basename) = ($fullname =~ /^(.*:)?(.*)/s);
    $dirpath = ':' unless $dirpath;
  }
  elsif ($type eq "AmigaOS") {
    ($dirpath,$basename) = ($fullname =~ /(.*[:\/])?(.*)/s);
    $dirpath = './' unless $dirpath;
  }
  elsif ($type eq 'VMS' ) {
    ($dirpath,$basename) = ($fullname =~ /^(.*[:>\]])?(.*)/s);
    $dirpath ||= '';  # should always be defined
  }
  else { # Default to Unix semantics.
    ($dirpath,$basename) = ($fullname =~ m{^(.*/)?(.*)}s);
    if ($orig_type eq 'VMS' and $fullname =~ m{^(/[^/]+/000000(/|$))(.*)}) {
      # dev:[000000] is top of VMS tree, similar to Unix '/'
      # so strip it off and treat the rest as "normal"
      my $devspec  = $1;
      my $remainder = $3;
      ($dirpath,$basename) = ($remainder =~ m{^(.*/)?(.*)}s);
      $dirpath ||= '';  # should always be defined
      $dirpath = $devspec.$dirpath;
    }
    $dirpath = './' unless $dirpath;
  }
      

  my $tail   = '';
  my $suffix = '';
  if (@suffices) {
    foreach $suffix (@suffices) {
      my $pat = ($igncase ? '(?i)' : '') . "($suffix)\$";
      if ($basename =~ s/$pat//s) {
        $taint .= substr($suffix,0,0);
        $tail = $1 . $tail;
      }
    }
  }

  # Ensure taint is propagated from the path to its pieces.
  $tail .= $taint;
  wantarray ? ($basename .= $taint, $dirpath .= $taint, $tail)
            : ($basename .= $taint);
}



=item C<basename>
X<basename> X<filename>

    my $filename = basename($path);
    my $filename = basename($path, @suffixes);

This function is provided for compatibility with the Unix shell command
C<basename(1)>.  It does B<NOT> always return the file name portion of a
path as you might expect.  To be safe, if you want the file name portion of
a path use C<fileparse()>.

C<basename()> returns the last level of a filepath even if the last
level is clearly directory.  In effect, it is acting like C<pop()> for
paths.  This differs from C<fileparse()>'s behaviour.

    # Both return "bar"
    basename("/foo/bar");
    basename("/foo/bar/");

@suffixes work as in C<fileparse()> except all regex metacharacters are
