const DATABASE = "nutritensor-demo-v1";
const STORE = "workspace";
let connection: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  if (!connection) {
    connection = new Promise((resolve, reject) => {
      const request = indexedDB.open(DATABASE, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE);
      request.onsuccess = () => {
        request.result.onversionchange = () => {
          request.result.close();
          connection = null;
        };
        resolve(request.result);
      };
      request.onerror = () => {
        connection = null;
        reject(
          new Error(
            "Browser storage is unavailable. Check private browsing settings.",
          ),
        );
      };
    });
  }
  return connection;
}

export async function read<T>(key: string, fallback: T): Promise<T> {
  const database = await open();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE, "readonly");
    const request = transaction.objectStore(STORE).get(key);
    request.onsuccess = () => resolve(request.result ?? fallback);
    request.onerror = () =>
      reject(new Error("Could not read the browser workspace"));
  });
}

export async function write<T>(key: string, value: T): Promise<T> {
  const database = await open();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE, "readwrite");
    transaction.objectStore(STORE).put(value, key);
    transaction.oncomplete = () => resolve(value);
    transaction.onerror = () =>
      reject(new Error("Could not save. Browser storage may be full."));
    transaction.onabort = () =>
      reject(new Error("The save transaction was interrupted"));
  });
}

export async function mutate<T>(
  key: string,
  fallback: T,
  transform: (value: T) => T,
): Promise<T> {
  const database = await open();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE, "readwrite");
    const store = transaction.objectStore(STORE);
    const request = store.get(key);
    let updated: T;
    request.onsuccess = () => {
      try {
        updated = transform(request.result ?? fallback);
        store.put(updated, key);
      } catch (error) {
        transaction.abort();
        reject(error);
      }
    };
    transaction.oncomplete = () => resolve(updated);
    transaction.onerror = () =>
      reject(new Error("Could not update the browser workspace"));
    transaction.onabort = () => reject(new Error("The update was interrupted"));
  });
}

export async function clear(): Promise<void> {
  const database = await open();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE, "readwrite");
    transaction.objectStore(STORE).clear();
    transaction.oncomplete = () => resolve();
    transaction.onerror = () =>
      reject(new Error("Could not clear the browser workspace"));
  });
}
