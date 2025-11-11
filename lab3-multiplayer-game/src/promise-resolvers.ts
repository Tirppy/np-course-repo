// Polyfill for Promise.withResolvers used by the skeleton code.
// Adds a factory that returns { promise, resolve, reject } for convenience.
// This file intentionally has side-effects (it mutates the global Promise object)
// so importing it at program start makes Promise.withResolvers available.

declare global {
    interface PromiseConstructor {
        withResolvers<T>(): { promise: Promise<T>; resolve: (v: T) => void; reject: (r?: any) => void };
    }
}

if (!(Promise as any).withResolvers) {
    (Promise as any).withResolvers = function<T>() {
        let resolve!: (v: T) => void;
        let reject!: (r?: any) => void;
        const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
        return { promise, resolve, reject };
    };
}

export {};
