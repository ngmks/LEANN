import {
    CharacterCodes,
    Comparer,
    Comparison,
    Debug,
    EqualityComparer,
    MapLike,
    Queue,
    SortedArray,
    SortedReadonlyArray,
    TextSpan,
} from "./_namespaces/ts.js";

/* eslint-disable @typescript-eslint/prefer-for-of */

/** @internal */
export const emptyArray: never[] = [] as never[];
/** @internal */
export const emptyMap: ReadonlyMap<never, never> = new Map<never, never>();

/** @internal */
export function length(array: readonly any[] | undefined): number {
    return array !== undefined ? array.length : 0;
}

/**
 * Iterates through 'array' by index and performs the callback on each element of array until the callback
 * returns a truthy value, then returns that value.
 * If no such value is found, the callback is applied to each element of array and undefined is returned.
 *
 * @internal
 */
export function forEach<T, U>(array: readonly T[] | undefined, callback: (element: T, index: number) => U | undefined): U | undefined {
    if (array !== undefined) {
        for (let i = 0; i < array.length; i++) {
            const result = callback(array[i], i);
            if (result) {
                return result;
            }
        }
    }
    return undefined;
}

/**
 * Like `forEach`, but iterates in reverse order.
 *
 * @internal
 */
export function forEachRight<T, U>(array: readonly T[] | undefined, callback: (element: T, index: number) => U | undefined): U | undefined {
    if (array !== undefined) {
        for (let i = array.length - 1; i >= 0; i--) {
            const result = callback(array[i], i);
            if (result) {
                return result;
            }
        }
    }
    return undefined;
}

/**
 * Like `forEach`, but suitable for use with numbers and strings (which may be falsy).
 *
 * @internal
 */
export function firstDefined<T, U>(array: readonly T[] | undefined, callback: (element: T, index: number) => U | undefined): U | undefined {
    if (array === undefined) {
        return undefined;
    }

    for (let i = 0; i < array.length; i++) {
        const result = callback(array[i], i);
        if (result !== undefined) {
            return result;
        }
    }
    return undefined;
}

/** @internal */
export function firstDefinedIterator<T, U>(iter: Iterable<T>, callback: (element: T) => U | undefined): U | undefined {
    for (const value of iter) {
        const result = callback(value);
        if (result !== undefined) {
            return result;
        }
    }
    return undefined;
}

/** @internal */
export function reduceLeftIterator<T, U>(iterator: Iterable<T> | undefined, f: (memo: U, value: T, i: number) => U, initial: U): U {
    let result = initial;
    if (iterator) {
        let pos = 0;
        for (const value of iterator) {
            result = f(result, value, pos);
            pos++;
        }
    }
    return result;
}

/** @internal */
export function zipWith<T, U, V>(arrayA: readonly T[], arrayB: readonly U[], callback: (a: T, b: U, index: number) => V): V[] {
    const result: V[] = [];
    Debug.assertEqual(arrayA.length, arrayB.length);
    for (let i = 0; i < arrayA.length; i++) {
        result.push(callback(arrayA[i], arrayB[i], i));
    }
    return result;
}

/**
 * Creates a new array with `element` interspersed in between each element of `input`
 * if there is more than 1 value in `input`. Otherwise, returns the existing array.
 *
 * @internal
 */
export function intersperse<T>(input: T[], element: T): T[] {
    if (input.length <= 1) {
        return input;
    }
    const result: T[] = [];
    for (let i = 0, n = input.length; i < n; i++) {
        if (i !== 0) result.push(element);
        result.push(input[i]);
    }
    return result;
}

/**
 * Iterates through `array` by index and performs the callback on each element of array until the callback
 * returns a falsey value, then returns false.
 * If no such value is found, the callback is applied to each element of array and `true` is returned.
 *
 * @internal
 */
export function every<T, U extends T>(array: readonly T[], callback: (element: T, index: number) => element is U): array is readonly U[];
/** @internal */
export function every<T, U extends T>(array: readonly T[] | undefined, callback: (element: T, index: number) => element is U): array is readonly U[] | undefined;
/** @internal */
export function every<T>(array: readonly T[] | undefined, callback: (element: T, index: number) => boolean): boolean;
export function every<T>(array: readonly T[] | undefined, callback: (element: T, index: number) => boolean): boolean {
    if (array !== undefined) {
        for (let i = 0; i < array.length; i++) {
            if (!callback(array[i], i)) {
                return false;
            }
        }
    }

    return true;
}

/**
 * Works like Array.prototype.find, returning `undefined` if no element satisfying the predicate is found.
 *
 * @internal
 */
export function find<T, U extends T>(array: readonly T[] | undefined, predicate: (element: T, index: number) => element is U, startIndex?: number): U | undefined;
/** @internal */
export function find<T>(array: readonly T[] | undefined, predicate: (element: T, index: number) => boolean, startIndex?: number): T | undefined;
/** @internal */
export function find<T>(array: readonly T[] | undefined, predicate: (element: T, index: number) => boolean, startIndex?: number): T | undefined {
    if (array === undefined) return undefined;
    for (let i = startIndex ?? 0; i < array.length; i++) {
        const value = array[i];
        if (predicate(value, i)) {
            return value;
        }
    }
    return undefined;
}

/** @internal */
export function findLast<T, U extends T>(array: readonly T[] | undefined, predicate: (element: T, index: number) => element is U, startIndex?: number): U | undefined;
/** @internal */
export function findLast<T>(array: readonly T[] | undefined, predicate: (element: T, index: number) => boolean, startIndex?: number): T | undefined;
/** @internal */
export function findLast<T>(array: readonly T[] | undefined, predicate: (element: T, index: number) => boolean, startIndex?: number): T | undefined {
    if (array === undefined) return undefined;
    for (let i = startIndex ?? array.length - 1; i >= 0; i--) {
        const value = array[i];
        if (predicate(value, i)) {
            return value;
        }
    }
    return undefined;
}

/**
 * Works like Array.prototype.findIndex, returning `-1` if no element satisfying the predicate is found.
 *
 * @internal
 */
export function findIndex<T>(array: readonly T[] | undefined, predicate: (element: T, index: number) => boolean, startIndex?: number): number {
    if (array === undefined) return -1;
    for (let i = startIndex ?? 0; i < array.length; i++) {
