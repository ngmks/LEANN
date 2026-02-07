const builtin = @import("builtin");
const std = @import("std.zig");
const float = @import("math/float.zig");
const assert = std.debug.assert;
const mem = std.mem;
const testing = std.testing;
const Alignment = std.mem.Alignment;

/// Euler's number (e)
pub const e = 2.71828182845904523536028747135266249775724709369995;

/// Archimedes' constant (π)
pub const pi = 3.14159265358979323846264338327950288419716939937510;

/// Phi or Golden ratio constant (Φ) = (1 + sqrt(5))/2
pub const phi = 1.6180339887498948482045868343656381177203091798057628621;

/// Circle constant (τ)
pub const tau = 2 * pi;

/// log2(e)
pub const log2e = 1.442695040888963407359924681001892137;

/// log10(e)
pub const log10e = 0.434294481903251827651128918916605082;

/// ln(2)
pub const ln2 = 0.693147180559945309417232121458176568;

/// ln(10)
pub const ln10 = 2.302585092994045684017991454684364208;

/// 2/sqrt(π)
pub const two_sqrtpi = 1.128379167095512573896158903121545172;

/// sqrt(2)
pub const sqrt2 = 1.414213562373095048801688724209698079;

/// 1/sqrt(2)
pub const sqrt1_2 = 0.707106781186547524400844362104849039;

/// pi/180.0
pub const rad_per_deg = 0.0174532925199432957692369076848861271344287188854172545609719144;

/// 180.0/pi
pub const deg_per_rad = 57.295779513082320876798154814105170332405472466564321549160243861;

pub const Sign = enum(u1) { positive, negative };
pub const FloatRepr = float.FloatRepr;
pub const floatExponentBits = float.floatExponentBits;
pub const floatMantissaBits = float.floatMantissaBits;
pub const floatFractionalBits = float.floatFractionalBits;
pub const floatExponentMin = float.floatExponentMin;
pub const floatExponentMax = float.floatExponentMax;
pub const floatTrueMin = float.floatTrueMin;
pub const floatMin = float.floatMin;
pub const floatMax = float.floatMax;
pub const floatEps = float.floatEps;
pub const floatEpsAt = float.floatEpsAt;
pub const inf = float.inf;
pub const nan = float.nan;
pub const snan = float.snan;

/// Performs an approximate comparison of two floating point values `x` and `y`.
/// Returns true if the absolute difference between them is less or equal than
/// the specified tolerance.
///
/// The `tolerance` parameter is the absolute tolerance used when determining if
/// the two numbers are close enough; a good value for this parameter is a small
/// multiple of `floatEps(T)`.
///
/// Note that this function is recommended for comparing small numbers
/// around zero; using `approxEqRel` is suggested otherwise.
///
/// NaN values are never considered equal to any value.
pub fn approxEqAbs(comptime T: type, x: T, y: T, tolerance: T) bool {
    assert(@typeInfo(T) == .float or @typeInfo(T) == .comptime_float);
    assert(tolerance >= 0);

    // Fast path for equal values (and signed zeros and infinites).
    if (x == y)
        return true;

    if (isNan(x) or isNan(y))
        return false;

    return @abs(x - y) <= tolerance;
}

/// Performs an approximate comparison of two floating point values `x` and `y`.
/// Returns true if the absolute difference between them is less or equal than
/// `max(|x|, |y|) * tolerance`, where `tolerance` is a positive number greater
/// than zero.
///
/// The `tolerance` parameter is the relative tolerance used when determining if
/// the two numbers are close enough; a good value for this parameter is usually
/// `sqrt(floatEps(T))`, meaning that the two numbers are considered equal if at
/// least half of the digits are equal.
///
/// Note that for comparisons of small numbers around zero this function won't
/// give meaningful results, use `approxEqAbs` instead.
///
/// NaN values are never considered equal to any value.
pub fn approxEqRel(comptime T: type, x: T, y: T, tolerance: T) bool {
    assert(@typeInfo(T) == .float or @typeInfo(T) == .comptime_float);
    assert(tolerance > 0);

    // Fast path for equal values (and signed zeros and infinites).
    if (x == y)
        return true;

    if (isNan(x) or isNan(y))
        return false;

    return @abs(x - y) <= @max(@abs(x), @abs(y)) * tolerance;
}

test approxEqAbs {
    inline for ([_]type{ f16, f32, f64, f128 }) |T| {
        const eps_value = comptime floatEps(T);
        const min_value = comptime floatMin(T);

        try testing.expect(approxEqAbs(T, 0.0, 0.0, eps_value));
        try testing.expect(approxEqAbs(T, -0.0, -0.0, eps_value));
        try testing.expect(approxEqAbs(T, 0.0, -0.0, eps_value));
        try testing.expect(!approxEqAbs(T, 1.0 + 2 * eps_value, 1.0, eps_value));
        try testing.expect(approxEqAbs(T, 1.0 + 1 * eps_value, 1.0, eps_value));
        try testing.expect(approxEqAbs(T, min_value, 0.0, eps_value * 2));
        try testing.expect(approxEqAbs(T, -min_value, 0.0, eps_value * 2));
    }

    comptime {
        // `comptime_float` is guaranteed to have the same precision and operations of
        // the largest other floating point type, which is f128 but it doesn't have a
        // defined layout so we can't rely on `@bitCast` to construct the smallest
        // possible epsilon value like we do in the tests above. In the same vein, we
        // also can't represent a max/min, `NaN` or `Inf` values.
        const eps_value = 1e-4;

        try testing.expect(approxEqAbs(comptime_float, 0.0, 0.0, eps_value));
        try testing.expect(approxEqAbs(comptime_float, -0.0, -0.0, eps_value));
        try testing.expect(approxEqAbs(comptime_float, 0.0, -0.0, eps_value));
        try testing.expect(!approxEqAbs(comptime_float, 1.0 + 2 * eps_value, 1.0, eps_value));
        try testing.expect(approxEqAbs(comptime_float, 1.0 + 1 * eps_value, 1.0, eps_value));
    }
}

test approxEqRel {
    inline for ([_]type{ f16, f32, f64, f128 }) |T| {
        const eps_value = comptime floatEps(T);
        const sqrt_eps_value = comptime sqrt(eps_value);
        const nan_value = comptime nan(T);
        const inf_value = comptime inf(T);
        const min_value = comptime floatMin(T);

        try testing.expect(approxEqRel(T, 1.0, 1.0, sqrt_eps_value));
        try testing.expect(!approxEqRel(T, 1.0, 0.0, sqrt_eps_value));
        try testing.expect(!approxEqRel(T, 1.0, nan_value, sqrt_eps_value));
        try testing.expect(!approxEqRel(T, nan_value, nan_value, sqrt_eps_value));
        try testing.expect(approxEqRel(T, inf_value, inf_value, sqrt_eps_value));
        try testing.expect(approxEqRel(T, min_value, min_value, sqrt_eps_value));
        try testing.expect(approxEqRel(T, -min_value, -min_value, sqrt_eps_value));
    }

    comptime {
        // `comptime_float` is guaranteed to have the same precision and operations of
        // the largest other floating point type, which is f128 but it doesn't have a
        // defined layout so we can't rely on `@bitCast` to construct the smallest
        // possible epsilon value like we do in the tests above. In the same vein, we
        // also can't represent a max/min, `NaN` or `Inf` values.
        const eps_value = 1e-4;
        const sqrt_eps_value = sqrt(eps_value);

        try testing.expect(approxEqRel(comptime_float, 1.0, 1.0, sqrt_eps_value));
        try testing.expect(!approxEqRel(comptime_float, 1.0, 0.0, sqrt_eps_value));
    }
}

pub fn raiseInvalid() void {
    // Raise INVALID fpu exception
}

pub fn raiseUnderflow() void {
    // Raise UNDERFLOW fpu exception
}

pub fn raiseOverflow() void {
    // Raise OVERFLOW fpu exception
}

pub fn raiseInexact() void {
    // Raise INEXACT fpu exception
}

pub fn raiseDivByZero() void {
    // Raise INEXACT fpu exception
}

pub const isNan = @import("math/isnan.zig").isNan;
pub const isSignalNan = @import("math/isnan.zig").isSignalNan;
