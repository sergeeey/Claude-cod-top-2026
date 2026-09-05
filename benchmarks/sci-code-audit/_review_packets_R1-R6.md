# Review packets R1-R6 (no ground truth — for blind Arm A / Arm B only)

## R1 — Python

**Context:** Method on `FITS_rec`, a NumPy `recarray` subclass representing the row data of a FITS binary table. This is the assignment path (`data[key] = value`) for table rows. `self._nfields` is the number of columns; `self.field(i)` returns column `i` as an array.

```python
    def __setitem__(self, key, value):
        if self._coldefs is None:
            return super().__setitem__(key, value)

        if isinstance(key, str):
            self[key][:] = value
            return

        if isinstance(key, slice):
            end = min(len(self), key.stop or len(self))
            end = max(0, end)
            start = max(0, key.start or 0)
            end = min(end, start + len(value))

            for idx in range(start, end):
                self.__setitem__(idx, value[idx - start])
            return

        if isinstance(value, FITS_record):
            for idx in range(self._nfields):
                self.field(self.names[idx])[key] = value.field(self.names[idx])
        elif isinstance(value, (tuple, list, np.void)):
            if self._nfields == len(value):
                for idx in range(self._nfields):
                    self.field(idx)[key] = value[idx]
            else:
                raise ValueError(
                    f"Input tuple or list required to have {self._nfields} elements."
                )
        else:
            raise TypeError(
                "Assignment requires a FITS_record, tuple, or list as input."
            )
```

---

## R2 — Python

**Context:** Cross-validation splitter machinery from a machine-learning library. `_BaseKFold` is the abstract base for K-fold splitters; `KFold` is the plain (non-stratified) implementation. `_num_samples(X)` returns the row count, `indexable()` coerces inputs to indexable containers, and `check_random_state(seed)` returns a `numpy.random.RandomState`.

```python
class _BaseKFold(BaseCrossValidator, metaclass=ABCMeta):
    """Base class for K-Fold cross-validators and TimeSeriesSplit."""

    @abstractmethod
    def __init__(self, n_splits, *, shuffle, random_state):
        if not isinstance(n_splits, numbers.Integral):
            raise ValueError(
                "The number of folds must be of Integral type. "
                "%s of type %s was passed." % (n_splits, type(n_splits))
            )
        n_splits = int(n_splits)

        if n_splits <= 1:
            raise ValueError(
                "k-fold cross-validation requires at least one"
                " train/test split by setting n_splits=2 or more,"
                " got n_splits={0}.".format(n_splits)
            )

        if not isinstance(shuffle, bool):
            raise TypeError("shuffle must be True or False; got {0}".format(shuffle))

        if not shuffle and random_state is not None:  # None is the default
            raise ValueError(
                (
                    "Setting a random_state has no effect since shuffle is "
                    "False. You should leave "
                    "random_state to its default (None), or set shuffle=True."
                ),
            )

        self.n_splits = n_splits
        self.shuffle = shuffle
        self.random_state = random_state

    def split(self, X, y=None, groups=None):
        """Generate indices to split data into training and test set."""
        X, y, groups = indexable(X, y, groups)
        n_samples = _num_samples(X)
        if self.n_splits > n_samples:
            raise ValueError(
                (
                    "Cannot have number of splits n_splits={0} greater"
                    " than the number of samples: n_samples={1}."
                ).format(self.n_splits, n_samples)
            )

        for train, test in super().split(X, y, groups):
            yield train, test


class KFold(_UnsupportedGroupCVMixin, _BaseKFold):

    def __init__(self, n_splits=5, *, shuffle=False, random_state=None):
        super().__init__(n_splits=n_splits, shuffle=shuffle, random_state=random_state)

    def _iter_test_indices(self, X, y=None, groups=None):
        n_samples = _num_samples(X)
        indices = np.arange(n_samples)
        if self.shuffle:
            check_random_state(self.random_state).shuffle(indices)

        n_splits = self.n_splits
        fold_sizes = np.full(n_splits, n_samples // n_splits, dtype=int)
        fold_sizes[: n_samples % n_splits] += 1
        current = 0
        for fold_size in fold_sizes:
            start, stop = current, current + fold_size
            yield indices[start:stop]
            current = stop
```

---

## R3 — Python

**Context:** A time-series transformer from a forecasting library, following the scikit-learn `fit` / `transform` estimator API. It fills missing values in a series. `_tags` is the estimator's capability declaration consumed by the base class. `BaseTransformer.transform()` dispatches to `_transform()`; `BaseTransformer.fit()` dispatches to `_fit()` unless the `fit_is_empty` tag says otherwise.

```python
    _tags = {
        "scitype:transform-input": "Series",
        "scitype:transform-output": "Series",
        "scitype:instancewise": True,
        "X_inner_mtype": ["pd.DataFrame", "pd.Series"],
        "y_inner_mtype": "None",
        "fit_is_empty": True,
        "handles-missing-data": True,
        "skip-inverse-transform": True,
        "univariate-only": False,
        "capability:missing_values:removes": True,
    }

    def _transform(self, X, y=None):
        """Transform X and return a transformed version."""
        self._check_method()
        Z = X.copy()

        if self.missing_values:
            Z = Z.replace(to_replace=self.missing_values, value=np.nan)

        if not _has_missing_values(Z):
            return Z

        if self.method == "random":
            if isinstance(Z, pd.DataFrame):
                for col in Z:
                    Z[col] = Z[col].apply(
                        lambda i: self._get_random(Z[col]) if np.isnan(i) else i
                    )
            else:
                Z = Z.apply(lambda i: self._get_random(Z) if np.isnan(i) else i)
        elif self.method == "constant":
            Z = Z.fillna(value=self.value)
        elif self.method in ["backfill", "bfill", "pad", "ffill"]:
            Z = Z.fillna(method=self.method)
        elif self.method == "drift":
            forecaster = PolynomialTrendForecaster(degree=1)
            Z = _impute_with_forecaster(forecaster, Z)
        elif self.method == "forecaster":
            forecaster = clone(self.forecaster)
            Z = _impute_with_forecaster(forecaster, Z)
        elif self.method == "mean":
            Z = Z.fillna(value=Z.mean())
        elif self.method == "median":
            Z = Z.fillna(value=Z.median())
        elif self.method in ["nearest", "linear"]:
            Z = Z.interpolate(method=self.method)
        else:
            raise ValueError(f"`method`: {self.method} not available.")
        Z = Z.fillna(method="ffill").fillna(method="backfill")
        return Z

    def _get_random(self, Z):
        """Create a random int or float value."""
        rng = check_random_state(self.random_state)
        if (Z.dropna() % 1 == 0).all():
            return rng.randint(Z.min(), Z.max())
        else:
            return rng.uniform(Z.min(), Z.max())


def _impute_with_forecaster(forecaster, Z):
    """Use a given forecaster for imputation by in-sample predictions."""
    if isinstance(Z, pd.Series):
        series = [Z]
    elif isinstance(Z, pd.DataFrame):
        series = [Z[column] for column in Z]

    for z in series:
        if _has_missing_values(z):
            na_index = z.index[z.isna()]
            fh = ForecastingHorizon(values=na_index, is_relative=False)
            forecaster.fit(y=z.fillna(method="ffill").fillna(method="backfill"), fh=fh)
            z[na_index] = forecaster.predict()
    return Z


def _has_missing_values(Z):
    return Z.isnull().to_numpy().any()
```

---

## R4 — Cython (`.pyx`, compiles to a C extension)

**Context:** The error-reporting path of a high-performance CSV reader. `self.parser` is a pointer to a C tokenizer struct. `tokenize_nrows` / `tokenize_all_rows` run the C tokenizer with the GIL released and return a negative status on failure. The C tokenizer obtains its input bytes by calling back into a Python file-like object's `read()`. Both excerpts are from the same file.

```cython
    # --- excerpt 1: the two callers ---

    cdef _tokenize_rows(self, size_t nrows):
        cdef int status
        with nogil:
            status = tokenize_nrows(self.parser, nrows)

        if self.parser.warn_msg != NULL:
            print >> sys.stderr, self.parser.warn_msg
            free(self.parser.warn_msg)
            self.parser.warn_msg = NULL

        if status < 0:
            raise_parser_error('Error tokenizing data', self.parser)

    cdef _read_rows(self, rows, bint trim):
        cdef:
            int buffered_lines
            int irows, footer = 0

        self._start_clock()

        if rows is not None:
            irows = rows
            buffered_lines = self.parser.lines - self.parser_start
            if buffered_lines < irows:
                self._tokenize_rows(irows - buffered_lines)

            if self.skip_footer > 0:
                raise ValueError('skip_footer can only be used to read '
                                 'the whole file')
        else:
            with nogil:
                status = tokenize_all_rows(self.parser)

            if self.parser.warn_msg != NULL:
                print >> sys.stderr, self.parser.warn_msg
                free(self.parser.warn_msg)
                self.parser.warn_msg = NULL

            if status < 0:
                raise_parser_error('Error tokenizing data', self.parser)
            footer = self.skip_footer

        if self.parser_start == self.parser.lines:
            raise StopIteration
        self._end_clock('Tokenization')
        ...


    # --- excerpt 2: the shared error helper, later in the same file ---

cdef raise_parser_error(object base, parser_t *parser):
    message = '%s. C error: ' % base
    if parser.error_msg != NULL:
        if PY3:
            message += parser.error_msg.decode('utf-8')
        else:
            message += parser.error_msg
    else:
        message += 'no error message set'

    raise CParserError(message)
```

---

## R5 — Python

**Context:** Two public functions from a standard-library statistics module. `fsum` is an exact-summation routine, `sumprod` computes a sum of pairwise products, `_rank` assigns ranks with ties averaged, `_sqrtprod(a, b)` computes `sqrt(a*b)` accurately, and `StatisticsError` is the module's own exception type.

```python
def covariance(x, y, /):
    """Covariance"""
    n = len(x)
    if len(y) != n:
        raise StatisticsError('covariance requires that both inputs have same number of data points')
    if n < 2:
        raise StatisticsError('covariance requires at least two data points')
    xbar = fsum(x) / n
    ybar = fsum(y) / n
    sxy = sumprod((xi - xbar for xi in x), (yi - ybar for yi in y))
    return sxy / (n - 1)


def correlation(x, y, /, *, method='linear'):
    """Pearson's correlation coefficient"""
    n = len(x)
    if len(y) != n:
        raise StatisticsError('correlation requires that both inputs have same number of data points')
    if n < 2:
        raise StatisticsError('correlation requires at least two data points')
    if method not in {'linear', 'ranked'}:
        raise ValueError(f'Unknown method: {method!r}')
    if method == 'ranked':
        start = (n - 1) / -2
        x = _rank(x, start=start)
        y = _rank(y, start=start)
    else:
        xbar = fsum(x) / n
        ybar = fsum(y) / n
        x = [xi - xbar for xi in x]
        y = [yi - ybar for yi in y]
    sxy = sumprod(x, y)
    sxx = sumprod(x, x)
    syy = sumprod(y, y)
    try:
        return sxy / _sqrtprod(sxx, syy)
    except ZeroDivisionError:
        raise StatisticsError('at least one of the inputs is constant')
```

---

## R6 — Python

**Context:** A dataset reader from an NLP training framework. The corpus is sharded across many files matched by a glob. `_instances` distributes shard filenames over a queue, spawns `num_workers` worker **processes** (`torch.multiprocessing.Process`) that each pull a shard and push parsed `Instance` objects onto an output queue, and yields those instances back to the training loop. `self.epochs_per_read` lets one `read()` call replay the corpus several times.

```python
    def read(self, file_path: str) -> Iterable[Instance]:
        outer_self = self

        class QIterable(Iterable[Instance]):
            def __init__(self) -> None:
                self.manager = Manager()
                self.output_queue = self.manager.Queue(outer_self.output_queue_size)
                self.num_workers = outer_self.num_workers

            def __iter__(self) -> Iterator[Instance]:
                return outer_self._instances(file_path, self.manager, self.output_queue)

        return QIterable()

    def _instances(self, file_path: str, manager: Manager, output_queue: Queue) -> Iterator[Instance]:
        """
        A generator that reads instances off the output queue and yields them up
        until none are left (signified by all ``num_workers`` workers putting their
        ids into the queue).
        """
        shards = glob.glob(file_path)
        num_shards = len(shards)

        input_queue = manager.Queue(num_shards * self.epochs_per_read + self.num_workers)
        for _ in range(self.epochs_per_read):
            random.shuffle(shards)
            for shard in shards:
                input_queue.put(shard)

        for _ in range(self.num_workers):
            input_queue.put(None)

        processes: List[Process] = []
        num_finished = 0

        for worker_id in range(self.num_workers):
            process = Process(target=_worker,
                              args=(self.reader, input_queue, output_queue, worker_id))
            logger.info(f"starting worker {worker_id}")
            process.start()
            processes.append(process)

        while num_finished < self.num_workers:
            item = output_queue.get()
            if isinstance(item, int):
                num_finished += 1
                logger.info(f"worker {item} finished ({num_finished}/{self.num_workers})")
            else:
                yield item

        for process in processes:
            process.join()
        processes.clear()
```
