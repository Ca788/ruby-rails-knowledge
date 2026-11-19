"""Verified official Ruby, Ruby on Rails, Ecosystem, and Security corpus + Knowledge Graph definitions."""
from __future__ import annotations

from typing import Any, Dict, List


def get_rails_corpus_documents() -> List[Dict[str, Any]]:
    """Return verified multi-version Rails official documentation entries (6.1, 7.0, 7.1, 7.2, 8.0, edge)."""
    docs: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. Active Record Callbacks & Transactions across Rails 6.1, 7.0, 7.1, 7.2, 8.0, edge
    # -------------------------------------------------------------------------
    for ver in ["6.1", "7.0", "7.1", "7.2", "8.0"]:
        v_url = f"https://guides.rubyonrails.org/v{ver}/active_record_callbacks.html"
        api_url = f"https://api.rubyonrails.org/v{ver}/classes/ActiveRecord/Callbacks.html"

        ver_specific_tx_note = ""
        if ver == "6.1":
            ver_specific_tx_note = (
                "In Rails 6.1, transaction callbacks (\x60after_commit\x60 and \x60after_rollback\x60) are defined on Active Record models "
                "(including aliases \x60after_create_commit\x60, \x60after_update_commit\x60, \x60after_save_commit\x60, and \x60after_destroy_commit\x60). "
                "Rails 6.1 does not include \x60ActiveRecord.after_all_transactions_commit\x60 (which was added in Rails 7.2); "
                "in Rails 6.1 projects, non-model code often uses model \x60after_commit\x60 hooks or gems like \x60after_commit_everywhere\x60."
            )
        elif ver in ("7.0", "7.1"):
            ver_specific_tx_note = (
                f"In Rails {ver}, \x60after_commit\x60 and \x60after_rollback\x60 execute after the outermost database transaction commits or rolls back. "
                f"When multiple \x60after_commit\x60 callbacks are registered on the same model in Rails {ver}, ordering can be controlled via "
                "\x60config.active_record.run_after_transaction_callbacks_in_order_defined\x60 (introduced in Rails 7.1)."
            )
        elif ver in ("7.2", "8.0"):
            ver_specific_tx_note = (
                f"In Rails {ver}, in addition to model-level \x60after_commit\x60 and \x60after_rollback\x60 callbacks, Rails provides "
                "\x60ActiveRecord.after_all_transactions_commit\x60 (introduced in Rails 7.2) to schedule callbacks from anywhere (such as service objects) "
                "that execute only after the outermost database transaction commits, or immediately if no transaction is open. "
                f"Additionally, in Rails {ver}, Active Job supports \x60enqueue_after_transaction_commit\x60 so \x60perform_later\x60 automatically defers "
                "job enqueueing until the surrounding Active Record transaction commits."
            )

        docs.append({
            "source_id": "rails_guides",
            "technology": "rails",
            "version": ver,
            "topic": "active_record",
            "doc_slug": "active_record_callbacks",
            "title": f"Active Record Callbacks (Rails {ver})",
            "source_url": v_url,
            "authority": "official",
            "related_concepts": ["callbacks", "after_commit", "after_save", "after_rollback", "transactions", "before_validation"],
            "markdown": f"""# Active Record Callbacks (Rails {ver})

## Callbacks Overview and Lifecycle Sequence

Callbacks are hooks into the life cycle of an Active Record object that allow you to trigger logic before or after an alteration of the object state in Rails {ver} ([{v_url}]({v_url})).

When saving an Active Record object (\x60save\x60, \x60save!\x60, \x60create\x60, \x60update\x60), the complete callback chain executes in this order inside a single database transaction:

1. \x60before_validation\x60
2. *[Validations run]*
3. \x60after_validation\x60
4. \x60before_save\x60
5. \x60around_save\x60
6. \x60before_create\x60 (or \x60before_update\x60 for existing records)
7. \x60around_create\x60 (or \x60around_update\x60)
8. *[Database INSERT or UPDATE SQL query executes]*
9. \x60after_create\x60 (or \x60after_update\x60)
10. \x60after_save\x60
11. *[Database Transaction COMMIT]*
12. \x60after_commit\x60 (or \x60after_rollback\x60 if the transaction rolled back)

Halting execution: If any \x60before_*\x60 callback throws \x60:abort\x60 (\x60throw :abort\x60), the callback chain is halted and the save/destroy operation is cancelled and rolled back.

## Difference Between after_save and after_commit

Understanding the difference between \x60after_save\x60 and \x60after_commit\x60 is critical for transactional integrity in Rails {ver} ([{api_url}]({api_url})):

| Aspect | \x60after_save\x60 | \x60after_commit\x60 |
| --- | --- | --- |
| **Transaction Boundary** | Runs **inside** the uncommitted database transaction. | Runs **outside** the database transaction, only after \x60COMMIT\x60 succeeds. |
| **Rollback Behavior** | If an exception occurs later in the same transaction (or an outer nested transaction), the DB change rolls back even though \x60after_save\x60 already ran. | Never runs if the transaction rolls back (use \x60after_rollback\x60 for rollback handling). |
| **Visibility to External Processes** | Other DB connections (like Sidekiq workers or external APIs) **cannot** see the uncommitted row yet (race condition / \x60ActiveRecord::RecordNotFound\x60). | Row is durable and visible to all database connections and background workers. |
| **Recommended Use Case** | Updating in-transaction records in the same database. | Enqueueing Active Job / Sidekiq jobs, sending emails, publishing webhooks, updating search indexes or caches. |

\x60\x60\x60ruby
class Order < ApplicationRecord
  # Runs INSIDE the DB transaction - unsafe for background jobs!
  after_save :recalculate_cached_totals

  # Runs ONLY AFTER the outermost DB transaction commits - safe for Sidekiq/ActiveJob/external I/O
  after_commit :enqueue_fulfillment_job, on: :create
  after_save_commit :sync_search_index
  after_destroy_commit :cleanup_external_storage
  after_rollback :log_failed_transaction

  private

  def enqueue_fulfillment_job
    OrderFulfillmentJob.perform_later(id)
  end
end
\x60\x60\x60

## Transaction Callbacks: after_commit and after_rollback (Rails {ver})

\x60after_commit\x60 and \x60after_rollback\x60 are triggered by the completion of the outermost database transaction in Rails {ver}.
Shorthand aliases include:
- \x60after_create_commit\x60 (equivalent to \x60after_commit ..., on: :create\x60)
- \x60after_update_commit\x60 (equivalent to \x60after_commit ..., on: :update\x60)
- \x60after_save_commit\x60 (equivalent to \x60after_commit ..., on: [:create, :update]\x60)
- \x60after_destroy_commit\x60 (equivalent to \x60after_commit ..., on: :destroy\x60)

{ver_specific_tx_note}
"""
        })

    # Edge version of callbacks
    docs.append({
        "source_id": "rails_edge_guides",
        "technology": "rails",
        "version": "edge",
        "topic": "active_record",
        "doc_slug": "active_record_callbacks_edge",
        "title": "Active Record Callbacks (Rails Edge)",
        "source_url": "https://edgeguides.rubyonrails.org/active_record_callbacks.html",
        "authority": "official_edge",
        "related_concepts": ["callbacks", "after_commit", "after_save", "transactions", "after_all_transactions_commit"],
        "markdown": """# Active Record Callbacks (Rails Edge)

## Edge Transaction Callbacks and ActiveRecord.after_all_transactions_commit

> **Note/Warning:** This documentation is from Rails Edge (unreleased main branch).

In Rails Edge, \x60after_commit\x60 and \x60ActiveRecord.after_all_transactions_commit\x60 coordinate with transactional job enqueueing. Model \x60after_commit\x60 hooks execute after the outermost database transaction commits, while \x60after_save\x60 executes before the transaction commits.
"""
    })

    # -------------------------------------------------------------------------
    # 2. Active Record Querying: N+1, includes vs preload vs eager_load, find_each, load_async
    # -------------------------------------------------------------------------
    for ver in ["6.1", "7.0", "7.1", "7.2", "8.0"]:
        q_url = f"https://guides.rubyonrails.org/v{ver}/active_record_querying.html"
        batches_api = f"https://api.rubyonrails.org/v{ver}/classes/ActiveRecord/Batches.html"

        strict_loading_details = (
            "In Rails 6.1, \x60strict_loading\x60 was introduced to prevent lazy loading of associations and raise "
            "\x60ActiveRecord::StrictLoadingViolationError\x60 whenever an association is accessed without eager loading. "
            "It can be enabled per relation (\x60User.strict_loading\x60), per record (\x60user.strict_loading!\x60), per association "
            "(\x60has_many :orders, strict_loading: true\x60), or globally via \x60config.active_record.strict_loading_by_default = true\x60. "
            "Note: In Rails 6.1 and 7.0, \x60strict_loading\x60 only supports the default \x60:all\x60 mode (\x60:n_plus_one_only\x60 mode was added in Rails 7.1)."
            if ver in ("6.1", "7.0")
            else
            f"In Rails {ver}, \x60strict_loading\x60 supports two modes: \x60:all\x60 (default, raises \x60ActiveRecord::StrictLoadingViolationError\x60 "
            "on any lazy load) and \x60mode: :n_plus_one_only\x60 (introduced in Rails 7.1, which allows single-record lazy loads like \x60belongs_to\x60 "
            "while raising on collection associations that cause N+1 queries): \x60user.strict_loading!(mode: :n_plus_one_only)\x60 or "
            "\x60config.active_record.strict_loading_mode = :n_plus_one_only\x60."
        )

        async_section = (
            "In Rails 6.1, asynchronous background query execution via \x60Relation#load_async\x60 is **not** available "
            "(it was introduced in Rails 7.0)."
            if ver == "6.1"
            else
            f"In Rails {ver}, \x60ActiveRecord::Relation#load_async\x60 schedules the SQL query to execute on a background thread pool "
            "configured by \x60config.active_record.async_query_executor\x60, allowing independent queries to run concurrently."
        )

        docs.append({
            "source_id": "rails_guides",
            "technology": "rails",
            "version": ver,
            "topic": "queries",
            "doc_slug": "active_record_querying",
            "title": f"Active Record Query Interface (Rails {ver})",
            "source_url": q_url,
            "authority": "official",
            "related_concepts": ["active_record", "n_plus_one", "includes", "preload", "eager_load", "strict_loading", "find_each", "associations"],
            "markdown": f"""# Active Record Query Interface (Rails {ver})

## Preventing N+1 Queries with Eager Loading and strict_loading

An **N+1 query problem** occurs when code executes 1 query to fetch $N$ parent records and then $N$ additional queries to fetch each parent record's associated records ([{q_url}]({q_url})).

Active Record in Rails {ver} prevents N+1 queries through two primary mechanisms:
1. **Eager Loading Associations** using \x60includes\x60, \x60preload\x60, or \x60eager_load\x60 on \x60ActiveRecord::Relation\x60 so associated records are loaded upfront in 1 or 2 queries instead of $N+1$ queries.
2. **Strict Loading (\x60strict_loading\x60)** to fail fast or log when an association is lazily loaded without eager loading.

{strict_loading_details}

\x60\x60\x60ruby
# Without eager loading (N+1 query problem: 1 + N queries)
books = Book.limit(10)
books.each {{ |book| puts book.author.last_name }}

# With eager loading (2 queries total: SELECT books + SELECT authors WHERE id IN (...))
books = Book.includes(:author).limit(10)
books.each {{ |book| puts book.author.last_name }}

# Enforcing strict_loading to forbid lazy N+1 queries
books = Book.strict_loading.includes(:author).limit(10)
\x60\x60\x60

## Difference Between includes, preload, and eager_load

Rails {ver} provides three eager loading methods on \x60ActiveRecord::Relation\x60: \x60includes\x60, \x60preload\x60, and \x60eager_load\x60 ([{q_url}]({q_url})):

| Method | SQL Strategy | Number of Queries | Can Filter/Order by Associated Table in \x60where\x60? |
| --- | --- | --- | --- |
| \x60preload(:posts)\x60 | Always executes **separate queries** (one for main model, one \x60WHERE id IN (...)\x60 per association). | 2+ queries | **No** — raises SQL error if \x60where\x60 references the associated table because it is not joined. |
| \x60eager_load(:posts)\x60 | Always executes a **single query** using \x60LEFT OUTER JOIN\x60 and instantiates both parent and associated models. | 1 query | **Yes** — associated table columns are available in \x60WHERE\x60 and \x60ORDER BY\x60. |
| \x60includes(:posts)\x60 | **Smart delegation**: defaults to \x60preload\x60 (separate queries), but switches to \x60eager_load\x60 (\x60LEFT OUTER JOIN\x60) if \x60where\x60 or \x60order\x60 references the associated table (with \x60references(:posts)\x60 when using string SQL conditions). | 2+ (default) or 1 (when joined) | **Yes** (use \x60.references(:posts)\x60 when passing raw SQL strings to \x60.where\x60). |

\x60\x60\x60ruby
# 1. preload: always separate queries
User.preload(:posts).to_a
# => SELECT "users".* FROM "users"
# => SELECT "posts".* FROM "posts" WHERE "posts"."user_id" IN (...)

# 2. eager_load: always single LEFT OUTER JOIN query
User.eager_load(:posts).where(posts: {{ published: true }}).to_a
# => SELECT "users"."id" AS t0_r0, ..., "posts"."id" AS t1_r0 ... FROM "users" LEFT OUTER JOIN "posts" ON ...

# 3. includes: delegates to preload unless associated table is filtered
User.includes(:posts).where(posts: {{ published: true }}).to_a
# With raw SQL strings, pair includes with references:
User.includes(:posts).where("posts.published = ?", true).references(:posts)
\x60\x60\x60

## Batch Processing: How find_each and in_batches Work

Iterating over a large table with \x60User.all.each\x60 instantiates all records in memory at once. \x60ActiveRecord::Batches\x60 ([{batches_api}]({batches_api})) provides \x60find_each\x60, \x60find_in_batches\x60, and \x60in_batches\x60 to process records in memory-bounded batches (default \x60batch_size: 1000\x60):

- **How \x60find_each\x60 works**: Under the hood, \x60find_each\x60 calls \x60find_in_batches\x60, retrieving up to \x60batch_size\x60 (1000) records at a time ordered by primary key ascending (\x60ORDER BY id ASC LIMIT 1000\x60) and using keyset pagination (\x60WHERE id > last_id\x60) instead of slow \x60OFFSET\x60 queries. It then yields each individual model instance to the block.
- **Ordering constraint**: Because \x60find_each\x60 relies on deterministic primary key ordering (\x60id > last_id\x60), any custom \x60.order(...)\x60 on the relation is ignored or raises a warning; you can control primary key direction via \x60order: :asc\x60 or \x60order: :desc\x60 (in Rails 6.1+) and range bounds via \x60start:\x60 and \x60finish:\x60.
- **\x60in_batches\x60**: Yields an \x60ActiveRecord::Relation\x60 for each batch rather than instantiated models, ideal for bulk \x60update_all\x60 or \x60delete_all\x60.

\x60\x60\x60ruby
# Process 1,000 records at a time using keyset pagination (WHERE id > last_id)
Customer.where(active: true).find_each(batch_size: 500, start: 1000, finish: 50_000) do |customer|
  CustomerMailer.weekly_digest(customer).deliver_later
end

# Bulk update in batches without instantiating Ruby objects
Customer.where(inactive_since: ..1.year.ago).in_batches(of: 1000).update_all(archived: true)
\x60\x60\x60

## Asynchronous Queries and ActiveRecord::Relation (Rails {ver})

\x60ActiveRecord::Relation\x60 uses lazy evaluation: chaining \x60where\x60, \x60includes\x60, \x60order\x60, and \x60limit\x60 does not execute SQL until the relation is enumerated or forced.

{async_section}
"""
        })

    # -------------------------------------------------------------------------
    # 3. Active Record Transactions & Connection Pooling across Rails 6.1..8.0
    # -------------------------------------------------------------------------
    for ver in ["6.1", "7.0", "7.1", "7.2", "8.0"]:
        tx_api = f"https://api.rubyonrails.org/v{ver}/classes/ActiveRecord/Transactions/ClassMethods.html"
        pool_api = f"https://api.rubyonrails.org/v{ver}/classes/ActiveRecord/ConnectionAdapters/ConnectionPool.html"

        docs.append({
            "source_id": "rails_api",
            "technology": "rails",
            "version": ver,
            "topic": "transactions",
            "doc_slug": "transactions_and_connection_pool",
            "title": f"Active Record Transactions and Database Connection Pooling (Rails {ver})",
            "source_url": tx_api,
            "authority": "official",
            "related_concepts": ["transactions", "nested_transactions", "savepoints", "after_commit", "connection_pool", "active_record"],
            "markdown": f"""# Active Record Transactions and Connection Pooling (Rails {ver})

## How Nested Transactions and Savepoints Work

In Rails {ver} ([{tx_api}]({tx_api})), \x60ActiveRecord::Base.transaction\x60 wraps database operations in an atomic transaction.

**Critical behavior of nested \x60transaction\x60 blocks:**
1. **Default nested calls share the parent transaction (no savepoint)**: By default, calling \x60transaction\x60 inside another \x60transaction\x60 block joins the existing open database transaction without issuing a new SQL transaction or savepoint.
2. **Surprising \x60ActiveRecord::Rollback\x60 trap**: In a default nested transaction (without \x60requires_new: true\x60), raising \x60ActiveRecord::Rollback\x60 in the inner block is rescued and swallowed by the inner \x60transaction\x60 method, allowing the **outer transaction to still COMMIT** both outer and inner changes!
3. **True sub-transactions with \x60requires_new: true\x60 (SQL \x60SAVEPOINT\x60)**: Passing \x60transaction(requires_new: true)\x60 instructs Active Record to issue a SQL \x60SAVEPOINT\x60 (and \x60ROLLBACK TO SAVEPOINT\x60 if \x60ActiveRecord::Rollback\x60 or an exception occurs), isolating the inner block's rollback while keeping the outer transaction alive.
4. **\x60joinable: false\x60**: If the outer transaction is opened with \x60joinable: false\x60, any nested \x60transaction\x60 call automatically uses a savepoint as if \x60requires_new: true\x60 were specified.

\x60\x60\x60ruby
User.transaction do
  User.create!(username: "Kotori")

  # Creates a SQL SAVEPOINT so rolling back the inner block does not corrupt or commit partial inner state
  User.transaction(requires_new: true) do
    User.create!(username: "Nemu")
    raise ActiveRecord::Rollback # Rolls back ONLY to the savepoint ("Nemu" is rolled back, "Kotori" commits)
  end
end
\x60\x60\x60

## How Rails Handles Database Connection Pooling

Rails {ver} manages database connections per process through \x60ActiveRecord::ConnectionAdapters::ConnectionPool\x60 ([{pool_api}]({pool_api})):

- **Thread-to-Connection Checkout**: Each pool maintains up to \x60pool\x60 connections (configured in \x60config/database.yml\x60, defaulting to \x605\x60). When a thread (e.g., a Puma web thread or Sidekiq worker thread) executes a query, it automatically checks out a connection from the pool and pins it to that thread/fiber for the duration of the request or execution block.
- **\x60checkout_timeout\x60**: If all \x60pool\x60 connections are busy, a requesting thread waits up to \x60checkout_timeout\x60 seconds (default \x605\x60 seconds) before raising \x60ActiveRecord::ConnectionTimeoutError\x60.
- **Sizing rule**: The \x60pool\x60 size in \x60config/database.yml\x60 must be at least equal to the maximum number of concurrent threads in the process (e.g., \x60RAILS_MAX_THREADS\x60 for Puma or Sidekiq \x60concurrency\x60).
- **Automatic Return & Reaper**: \x60ActiveRecord::ConnectionAdapters::ConnectionManagement\x60 middleware (and \x60Rails.application.executor\x60) returns connections to the pool at the end of each HTTP request or Active Job execution. A background \x60Reaper\x60 (configured via \x60reaping_frequency\x60) periodically reclaims connections leaked by dead threads and prunes connections idle longer than \x60idle_timeout\x60 (default 300s).
- **Explicit \x60with_connection\x60**: Background threads can lease and immediately release a connection using \x60ActiveRecord::Base.connection_pool.with_connection {{ |conn| ... }}\x60.
"""
        })

    # -------------------------------------------------------------------------
    # 4. Associations (dependent: :destroy vs :delete_all, strict_loading, inverse_of)
    # -------------------------------------------------------------------------
    for ver in ["6.1", "7.0", "7.1", "7.2", "8.0"]:
        assoc_url = f"https://guides.rubyonrails.org/v{ver}/association_basics.html"
        docs.append({
            "source_id": "rails_guides",
            "technology": "rails",
            "version": ver,
            "topic": "associations",
            "doc_slug": "association_basics",
            "title": f"Active Record Associations (Rails {ver})",
            "source_url": assoc_url,
            "authority": "official",
            "related_concepts": ["associations", "dependent_destroy", "callbacks", "strict_loading", "active_record"],
            "markdown": f"""# Active Record Associations (Rails {ver})

## Association Types and dependent: :destroy Options

In Rails {ver} ([{assoc_url}]({assoc_url})), associations declare relationships between Active Record models (\x60belongs_to\x60, \x60has_one\x60, \x60has_many\x60, \x60has_many :through\x60, \x60has_one :through\x60, \x60has_and_belongs_to_many\x60).

### Controlling Associated Record Lifecycle with \x60dependent:\x60

When destroying a parent record, the \x60dependent:\x60 option on \x60has_many\x60 / \x60has_one\x60 / \x60belongs_to\x60 controls what happens to associated objects:

- \x60dependent: :destroy\x60 — Instantiates each associated object and calls its \x60#destroy\x60 method inside the transaction, **executing all \x60before_destroy\x60, \x60after_destroy\x60, and \x60after_destroy_commit\x60 callbacks** and cascading to grandchildren.
- \x60dependent: :delete_all\x60 (or \x60:delete\x60 for \x60has_one\x60) — Deletes associated rows directly in SQL (\x60DELETE FROM ... WHERE parent_id = ?\x60) **without instantiating models or running any destroy callbacks**.
- \x60dependent: :nullify\x60 — Sets the foreign key column to \x60NULL\x60 in SQL (\x60UPDATE ... SET parent_id = NULL\x60) without running callbacks.
- \x60dependent: :destroy_async\x60 — Enqueues \x60ActiveRecord::DestroyAssociationAsyncJob\x60 to destroy associated records in the background (do not use if backed by a DB-level foreign key \x60ON DELETE\x60 constraint).
- \x60dependent: :restrict_with_exception\x60 / \x60:restrict_with_error\x60 — Prevents deletion if associated records exist.

\x60\x60\x60ruby
class Author < ApplicationRecord
  has_many :books, dependent: :destroy, inverse_of: :author, strict_loading: true
  has_many :audit_logs, dependent: :delete_all
  has_many :drafts, dependent: :nullify
end
\x60\x60\x60
"""
        })

    # -------------------------------------------------------------------------
    # 5. Zeitwerk Autoloading & Reloading Constants across Rails 6.1..8.0
    # -------------------------------------------------------------------------
    for ver in ["6.1", "7.0", "7.1", "7.2", "8.0"]:
        auto_url = f"https://guides.rubyonrails.org/v{ver}/autoloading_and_reloading_constants.html"
        mode_note = (
            "In Rails 6.1, **Zeitwerk** is the default autoloader for \x60config.load_defaults 6.0\x60 and \x606.1\x60, while the legacy "
            "\x60:classic\x60 autoloader (\x60config.autoloader = :classic\x60) is **deprecated** and emits deprecation warnings before its removal in Rails 7.0."
            if ver == "6.1"
            else
            f"In Rails {ver}, **Zeitwerk** is the sole autoloader. The legacy \x60:classic\x60 autoloader was completely removed in Rails 7.0; "
            "setting \x60config.autoloader = :classic\x60 is no longer supported."
        )
        docs.append({
            "source_id": "rails_guides",
            "technology": "rails",
            "version": ver,
            "topic": "autoloading",
            "doc_slug": "autoloading_and_reloading_constants",
            "title": f"Autoloading and Reloading Constants with Zeitwerk (Rails {ver})",
            "source_url": auto_url,
            "authority": "official",
            "related_concepts": ["zeitwerk", "autoloading", "classic_autoloader", "configuration"],
            "markdown": f"""# Autoloading and Reloading Constants (Zeitwerk) — Rails {ver}

## How Zeitwerk Autoloading Works

{mode_note}

Zeitwerk ([{auto_url}]({auto_url})) works by **scanning the project's autoload paths upfront** (using Ruby's native \x60Module#autoload\x60) rather than intercepting \x60const_missing\x60 at runtime:

1. **File-to-Constant Mapping (Inflection-Driven)**: Unlike \x60:classic\x60 which guessed file paths from missing constants, Zeitwerk walks \x60config.autoload_paths\x60 (all subdirectories of \x60app/\x60 except \x60assets\x60, \x60javascript\x60, \x60views\x60) and maps each file path to the exact constant it must define using \x60String#camelize\x60:
   - \x60app/models/user.rb\x60 $\rightarrow$ \x60User\x60
   - \x60app/controllers/admin/users_controller.rb\x60 $\rightarrow$ \x60Admin::UsersController\x60
   - Subdirectories represent implicit module namespaces (\x60app/services/billing/invoice.rb\x60 $\rightarrow$ \x60Billing::Invoice\x60).
2. **Thread-Safe \x60Module#autoload\x60**: Zeitwerk sets standard Ruby \x60autoload\x60 hooks on parent modules/Object, eliminating the \x60const_missing\x60 nesting order bugs and race conditions of the classic loader.
3. **Custom Acronyms & Inflections**: Custom casing (e.g., \x60HTMLParser\x60 in \x60html_parser.rb\x60) is configured via \x60ActiveSupport::Inflector.inflections(:en) {{ |inflect| inflect.acronym "HTML" }}\x60 or \x60Rails.autoloaders.main.inflector.inflect(...)\x60.
4. **Eager Loading & Verification**: In production (\x60config.eager_load = true\x60), Zeitwerk eager-loads all files on boot. You can verify compliance in any environment by running \x60bin/rails zeitwerk:check\x60.
"""
        })

    # -------------------------------------------------------------------------
    # 6. Deprecations, Release Notes & API Changes between Rails 6.1 and 7.2 / 8.0
    # -------------------------------------------------------------------------
    for ver in ["6.1", "7.0", "7.1", "7.2", "8.0"]:
        upg_url = f"https://guides.rubyonrails.org/v{ver}/upgrading_ruby_on_rails.html"
        dep_api = f"https://api.rubyonrails.org/v{ver}/classes/ActiveSupport/Deprecation.html"
        docs.append({
            "source_id": "rails_guides",
            "technology": "rails",
            "version": ver,
            "topic": "configuration",
            "doc_slug": "upgrading_and_deprecations",
            "title": f"Upgrading Ruby on Rails, API Changes, and Deprecations (Rails {ver})",
            "source_url": upg_url,
            "authority": "official",
            "related_concepts": ["deprecations", "active_support", "callbacks", "after_all_transactions_commit", "strict_loading", "zeitwerk"],
            "markdown": f"""# Upgrading Ruby on Rails & Deprecation System (Rails {ver})

## What Changed Between Rails 6.1 and Rails 7.2 / 8.0 Across Core APIs

Key API evolutions between Rails 6.1 and Rails 7.2+ ([{upg_url}]({upg_url})):

| API / Feature Area | Rails 6.1 Behavior | Rails 7.0 / 7.1 Behavior | Rails 7.2 / 8.0 Behavior |
| --- | --- | --- | --- |
| **Transaction Callbacks** | Model-only \x60after_commit\x60 / \x60after_rollback\x60 hooks. | \x60run_after_transaction_callbacks_in_order_defined\x60 added in 7.1. | **\x60ActiveRecord.after_all_transactions_commit\x60** added in 7.2 to run callbacks outside models; Active Job \x60enqueue_after_transaction_commit\x60 enabled. |
| **\x60strict_loading\x60** | Introduced in 6.1 (raises on all lazy loads). | Enabled per model/relation/association. | Added **\x60mode: :n_plus_one_only\x60** (7.1+) to only block collection N+1 queries while allowing single \x60belongs_to\x60 loads. |
| **Autoloading** | Zeitwerk default; \x60:classic\x60 autoloader deprecated. | \x60:classic\x60 autoloader **removed**; Zeitwerk is mandatory. | Zeitwerk with \x60config.autoload_lib(ignore: ...)\x60 for \x60lib/\x60 directory. |
| **\x60ActiveSupport::Deprecation\x60** | Global singleton \x60ActiveSupport::Deprecation.warn(...)\x60 and \x60deprecate_methods\x60. | In 7.1, calling singleton \x60ActiveSupport::Deprecation.warn\x60 is **deprecated** in favor of \x60ActiveSupport::Deprecation.new\x60 and \x60Rails.application.deprecators\x60. | Global singleton delegation removed in 7.2; libraries must use their own \x60ActiveSupport::Deprecation.new\x60 instance registered in \x60app.deprecators[:my_gem]\x60. |
| **Async Queries & Jobs** | Synchronous \x60Relation\x60 queries; single \x60perform_later\x60. | \x60Relation#load_async\x60 (7.0) and \x60ActiveJob.perform_all_later\x60 (7.1). | YJIT enabled by default in 7.2; Solid Queue default in 8.0. |

## How Deprecated Methods Are Documented and Handled (ActiveSupport::Deprecation)

In Official Rails API documentation and source code ([{dep_api}]({dep_api})), deprecated methods are documented and instrumented through three standardized layers:

1. **RDoc / API Documentation Tags & Release Notes**:
   - In RDoc comments, deprecated methods carry an explicit \x60DEPRECATED:\x60 notice or \x60:nodoc:\x60 marker stating the replacement API and target removal release (e.g., *"DEPRECATED: Use \x60ActiveSupport::Deprecation.new\x60 instead. Will be removed in Rails 7.2."*).
   - Every minor release's *Release Notes* and *Upgrading Ruby on Rails* guide includes a dedicated **Deprecations** section per framework (Active Record, Active Support, Action Pack).
2. **Runtime Instrumentation via \x60ActiveSupport::Deprecation\x60**:
   - Methods are wrapped with \x60deprecate :old_method, deprecator: ...\x60 or explicit \x60deprecator.warn("...")\x60.
   - In **Rails 6.1 and 7.0**, warnings used the global singleton \x60ActiveSupport::Deprecation.warn\x60.
   - In **Rails 7.1 and 7.2+**, deprecations use isolated \x60ActiveSupport::Deprecation.new("8.0", "MyGem")\x60 instances managed via \x60Rails.application.deprecators\x60.
3. **Configurable Deprecation Behaviors (\x60config.active_support.deprecation\x60)**:
   - \x60:log\x60 (default in development: writes to \x60Rails.logger\x60), \x60:stderr\x60, \x60:notify\x60 (publishes \x60deprecation.rails\x60 via \x60ActiveSupport::Notifications\x60), \x60:raise\x60 (raises \x60ActiveSupport::DeprecationException\x60 in test/CI to catch deprecated calls early), or \x60:silence\x60.
   - Disallowed deprecations can be configured via \x60config.active_support.disallowed_deprecation = :raise\x60 and \x60config.active_support.disallowed_deprecation_warnings\x60.
"""
        })

    # -------------------------------------------------------------------------
    # 7. Active Job, Active Support, Action Controller, Routing, Middleware, Security, Performance, Testing
    # -------------------------------------------------------------------------
    for ver in ["6.1", "7.2", "8.0"]:
        docs.append({
            "source_id": "rails_guides",
            "technology": "rails",
            "version": ver,
            "topic": "active_job",
            "doc_slug": "active_job_and_controllers",
            "title": f"Active Job, Action Controller, Routing, Middleware, and Active Support (Rails {ver})",
            "source_url": f"https://guides.rubyonrails.org/v{ver}/active_job_basics.html",
            "authority": "official",
            "related_concepts": ["active_job", "action_controller", "active_support", "routing", "middleware", "after_commit"],
            "markdown": f"""# Active Job, Action Controller, Routing, Middleware & Active Support (Rails {ver})

## Active Job Queueing, Retries, and Transaction Safety

\x60ActiveJob::Base\x60 provides a unified interface across queue adapters (\x60:sidekiq\x60, \x60:solid_queue\x60, \x60:async\x60, \x60:test\x60) in Rails {ver}:
- Enqueue with \x60MyJob.perform_later(record)\x60 or \x60MyJob.set(wait: 5.minutes, queue: :critical).perform_later(record)\x60.
- Arguments are serialized via **GlobalID** (\x60gid://app/Model/id\x60); if a job is enqueued inside an uncommitted transaction (e.g. in \x60after_save\x60 instead of \x60after_commit\x60), the worker may fail with \x60ActiveJob::DeserializationError\x60 (wrapping \x60ActiveRecord::RecordNotFound\x60). Always enqueue jobs in \x60after_commit\x60 (or rely on \x60enqueue_after_transaction_commit\x60 in Rails 7.2+).
- Declarative error handling: \x60retry_on CustomError, wait: :exponentially_longer, attempts: 5\x60 and \x60discard_on ActiveJob::DeserializationError\x60.

## Action Controller, Strong Parameters, Routing, and Rack Middleware

- **Action Controller & Strong Parameters**: Controllers use \x60before_action\x60, \x60around_action\x60, and \x60after_action\x60 filters. Mass-assignment protection requires whitelisting attributes with \x60params.require(:user).permit(:name, :email)\x60 (and \x60params.expect(user: [:name, :email])\x60 introduced in Rails 8.0).
- **Routing**: Defined in \x60config/routes.rb\x60 using \x60resources :articles\x60, \x60namespace\x60, \x60scope\x60, \x60member\x60, \x60collection\x60, and route constraints.
- **Rack Middleware**: Inspected via \x60bin/rails middleware\x60 and configured via \x60config.middleware.use\x60, \x60insert_before\x60, \x60insert_after\x60, or \x60delete\x60.
- **Active Support Core Extensions**: Provides \x60Object#blank?\x60, \x60Object#present?\x60, \x60Object#presence\x60, \x60Object#try\x60, \x60ActiveSupport::Concern\x60, \x60ActiveSupport::Notifications\x60, and \x60ActiveSupport::CurrentAttributes\x60.

## Rails Security, Performance Caching, and Testing Conventions

- **Security**: Always parameterize SQL conditions (\x60where("email = ?", email)\x60 or hash conditions \x60where(email: email)\x60) to prevent SQL injection; use \x60protect_from_forgery with: :exception\x60 for CSRF protection.
- **Performance & Caching**: Use Russian Doll fragment caching (\x60cache record do ... end\x60 with \x60touch: true\x60 on \x60belongs_to\x60), low-level caching (\x60Rails.cache.fetch\x60), and connection pooling.
- **Testing**: Built-in Minitest support (\x60ActiveSupport::TestCase\x60, \x60ActionDispatch::IntegrationTest\x60) runs each test inside a database transaction rolled back on completion.
"""
        })

    return docs


def get_ruby_corpus_documents() -> List[Dict[str, Any]]:
    """Return verified multi-version Ruby official documentation entries (3.1, 3.2, 3.3, 3.4)."""
    docs: List[Dict[str, Any]] = []

    for ver in ["3.1", "3.2", "3.3", "3.4"]:
        enum_url = f"https://docs.ruby-lang.org/en/{ver}/Enumerable.html"
        obj_url = f"https://docs.ruby-lang.org/en/{ver}/Object.html"
        conc_url = f"https://docs.ruby-lang.org/en/{ver}/Thread.html"
        gc_url = f"https://docs.ruby-lang.org/en/{ver}/GC.html"

        ver_highlight = {
            "3.1": "Ruby 3.1 features experimental YJIT, the new \x60debug\x60 gem, hash shorthand syntax \x60{x:, y:}\x60, and anonymous block forwarding \x60def foo(&); bar(&); end\x60.",
            "3.2": "Ruby 3.2 introduces the immutable \x60Data.define\x60 value class, \x60Regexp.timeout\x60 for ReDoS protection, production-ready YJIT, and WASI WebAssembly support.",
            "3.3": "Ruby 3.3 introduces the **Prism** portable parser gem, M:N thread scheduler, Lrama LALR parser generator, RJIT, and major YJIT memory/speed improvements (including inlining \x60#blank?\x60).",
            "3.4": "Ruby 3.4 makes **Prism** the default parser, adds \x60it\x60 as the implicit single block parameter (e.g. \x60ary.map { it.upcase }\x60), introduces chilled string literals emitting warnings on mutation without \x60frozen_string_literal\x60, and adds Happy Eyeballs v2 in \x60Net::HTTP\x60.",
        }[ver]

        docs.append({
            "source_id": "ruby_api",
            "technology": "ruby",
            "version": ver,
            "topic": "enumerable",
            "doc_slug": "enumerable_api",
            "title": f"Ruby Enumerable Module and Methods (Ruby {ver})",
            "source_url": enum_url,
            "authority": "official",
            "related_concepts": ["enumerable", "enumerator", "ruby_language", "collections"],
            "markdown": f"""# Ruby Enumerable Module and Methods (Ruby {ver})

## What Are the Ruby Enumerable Methods?

The \x60Enumerable\x60 mixin ([{enum_url}]({enum_url})) provides collection traversal, searching, sorting, filtering, and aggregation methods to any class (such as \x60Array\x60, \x60Hash\x60, \x60Range\x60, \x60Set\x60) that implements \x60#each\x60. For sorting methods (\x60#sort\x60, \x60#max\x60, \x60#min\x60), elements must also implement the spaceship operator \x60<=>\x60.

### Core Categories of Ruby \x60Enumerable\x60 Methods (Ruby {ver})

1. **Transformation & Mapping**:
   - \x60#map\x60 / \x60#collect\x60 — Returns a new array with the results of running the block once for every element.
   - \x60#flat_map\x60 / \x60#collect_concat\x60 — Maps and flattens the result by one level.
   - \x60#filter_map\x60 — Maps and retains only truthy results in a single pass.
2. **Filtering & Partitioning**:
   - \x60#select\x60 / \x60#filter\x60 (and \x60#find_all\x60) — Returns all elements for which the block returns truthy.
   - \x60#reject\x60 — Returns all elements for which the block returns false/nil.
   - \x60#grep(pattern)\x60 and \x60#grep_v(pattern)\x60 — Filters elements matching (or not matching) \x60pattern === element\x60.
   - \x60#partition\x60 — Splits elements into two arrays: \x60[matching, non_matching]\x60.
   - \x60#group_by\x60 — Groups elements into a Hash keyed by the block's return value.
   - \x60#uniq\x60 — Returns unique elements.
3. **Searching & Predicates**:
   - \x60#find\x60 / \x60#detect\x60 — Returns the first element matching the block.
   - \x60#any?\x60, \x60#all?\x60, \x60#none?\x60, \x60#one?\x60 — Boolean predicate checks across elements (accept an optional pattern argument using \x60===\x60).
   - \x60#include?\x60 / \x60#member?\x60 — Tests membership via \x60==\x60.
4. **Aggregation & Reduction**:
   - \x60#reduce\x60 / \x60#inject\x60 — Combines all elements by applying a binary operation or accumulator block.
   - \x60#each_with_object(memo)\x60 — Iterates with a mutable memo object and returns \x60memo\x60.
   - \x60#tally\x60 — Counts occurrences of each distinct element and returns a frequency Hash (accepts an optional destination hash in Ruby 3.1+).
   - \x60#sum\x60, \x60#count\x60, \x60#min\x60, \x60#max\x60, \x60#minmax\x60, \x60#min_by\x60, \x60#max_by\x60.
5. **Sorting, Slicing & Lazy Evaluation**:
   - \x60#sort\x60, \x60#sort_by\x60 — Sorts elements (Schwarzian transform in \x60#sort_by\x60).
   - \x60#take(n)\x60, \x60#take_while\x60, \x60#drop(n)\x60, \x60#drop_while\x60, \x60#each_slice(n)\x60, \x60#each_cons(n)\x60, \x60#chunk\x60, \x60#slice_when\x60.
   - \x60#lazy\x60 — Returns an \x60Enumerator::Lazy\x60 that pipelines \x60map\x60/\x60select\x60/\x60take\x60 without allocating intermediate arrays, essential for large or infinite streams.

\x60\x60\x60ruby
# Chaining Enumerable methods in Ruby {ver}
totals_by_role = users
  .filter_map {{ |u| u if u.active? }}
  .group_by(&:role)
  .transform_values {{ |list| list.sum(&:score) }}

# Frequency counting with #tally
["ruby", "rails", "ruby"].tally # => {{"ruby" => 2, "rails" => 1}}

# Lazy evaluation on large streams
File.foreach("large.log").lazy.grep(/ERROR/).map(&:strip).first(10)
\x60\x60\x60
"""
        })

        docs.append({
            "source_id": "ruby_api",
            "technology": "ruby",
            "version": ver,
            "topic": "object_model",
            "doc_slug": "object_model_exceptions_stdlib",
            "title": f"Ruby Object Model, Classes, Modules, Exceptions & Standard Library (Ruby {ver})",
            "source_url": obj_url,
            "authority": "official",
            "related_concepts": ["object_model", "classes_modules", "exceptions", "stdlib", "ruby_language"],
            "markdown": f"""# Ruby Object Model, Classes, Modules, Exceptions & Stdlib (Ruby {ver})

## Ruby Object Model, Ancestor Chain, and Classes vs Modules

In Ruby {ver} ([{obj_url}]({obj_url})), every value is an object and every class is an instance of \x60Class\x60 (which inherits from \x60Module\x60 $\rightarrow$ \x60Object\x60 $\rightarrow$ \x60Kernel\x60 $\rightarrow$ \x60BasicObject\x60).

- **Method Lookup Path (\x60Module#ancestors\x60)**: When a method is called on an object, Ruby searches:
  1. The object's **singleton class** (eigenclass, including modules added via \x60extend\x60).
  2. Modules prepended to the class via \x60prepend\x60 (in reverse order of prepending).
  3. The class itself.
  4. Modules included in the class via \x60include\x60 (in reverse order of inclusion).
  5. The superclass chain up to \x60Object\x60, \x60Kernel\x60, and \x60BasicObject\x60.
- **\x60include\x60 vs \x60prepend\x60 vs \x60extend\x60**: \x60include\x60 inserts a module *after* the class in \x60ancestors\x60; \x60prepend\x60 inserts it *before* the class (allowing wrapper methods with \x60super\x60); \x60extend\x60 mixes the module into the receiver's singleton class.

## Ruby Exception Hierarchy and Error Handling

- **Always Rescue \x60StandardError\x60, Never Bare \x60Exception\x60**: A bare \x60rescue\x60 catches \x60StandardError\x60 and its subclasses (\x60ArgumentError\x60, \x60RuntimeError\x60, \x60NoMethodError\x60, \x60NameError\x60, \x60IOError\x60). Rescuing \x60Exception\x60 directly traps system-level signals like \x60SignalException\x60 (\x60SIGINT\x60), \x60SystemExit\x60, and \x60NoMemoryError\x60, breaking process shutdown.
- **Chained Exceptions**: \x60Exception#cause\x60 automatically records the active exception when a new exception is raised inside a \x60rescue\x60 block.

## Ruby {ver} Release Notes & Standard Library Highlights

{ver_highlight}
"""
        })

        docs.append({
            "source_id": "ruby_api",
            "technology": "ruby",
            "version": ver,
            "topic": "concurrency",
            "doc_slug": "concurrency_and_memory_management",
            "title": f"Ruby Concurrency (Thread, Fiber, Ractor) and Memory Management / GC (Ruby {ver})",
            "source_url": conc_url,
            "authority": "official",
            "related_concepts": ["concurrency", "memory_management", "yjit", "ruby_language"],
            "markdown": f"""# Ruby Concurrency and Memory Management (Ruby {ver})

## Concurrency Primitives: Thread, Fiber::Scheduler, and Ractor

In CRuby {ver} ([{conc_url}]({conc_url})), three concurrency abstractions address different workloads:
- **\x60Thread\x60 and GVL**: Native OS threads synchronized by the Global VM Lock (GVL). When a thread performs blocking I/O (socket, database query, file read), it releases the GVL so other threads execute concurrently. Synchronization uses \x60Thread::Mutex\x60, \x60Thread::Queue\x60, and \x60ConditionVariable\x60.
- **\x60Fiber\x60 and \x60Fiber::Scheduler\x60**: Lightweight cooperative coroutines for event-driven non-blocking I/O without thread context-switching overhead.
- **\x60Ractor\x60**: Actor-model isolated execution units that each hold their own GVL for true multi-core CPU parallelism by restricting shared mutable state (only shareable/deeply frozen objects or message passing via \x60Ractor#send\x60 / \x60Ractor.receive\x60).

## Memory Management, Generational GC, Compaction, and YJIT

Ruby {ver} ([{gc_url}]({gc_url})) uses a generational, incremental, tri-color mark-and-sweep Garbage Collector (RGenGC / RIncGC) with **Variable Width Allocation (VWA)** (in Ruby 3.2+) and heap compaction (\x60GC.compact\x60 / \x60GC.auto_compact\x60) to minimize fragmentation and Copy-on-Write (CoW) page invalidation in preforking servers like Puma.
"""
        })

    return docs


def get_ecosystem_and_security_documents() -> List[Dict[str, Any]]:
    """Return complementary ecosystem (Ruby Style Guide, RuboCop, RSpec) and OWASP Security corpus."""
    return [
        {
            "source_id": "ruby_style_guide",
            "technology": "ecosystem",
            "version": "current",
            "topic": "ruby_language",
            "doc_slug": "ruby_style_guide_conventions",
            "title": "The Ruby Style Guide — Community Coding Conventions",
            "source_url": "https://rubystyle.guide/",
            "authority": "community_standard",
            "related_concepts": ["ruby_style_guide", "rubocop", "enumerable", "exceptions"],
            "markdown": """# The Ruby Style Guide (Community Standard)

## Core Ruby Style Conventions and Idioms

> **Note/Warning:** Community style standard ([https://rubystyle.guide/](https://rubystyle.guide/)) — classified as \x60community_standard\x60, distinct from official Ruby language specifications.

- Prefer \x60map\x60 over \x60collect\x60, \x60find\x60 over \x60detect\x60, \x60select\x60 over \x60find_all\x60, \x60reduce\x60 over \x60inject\x60, and \x60size\x60 over \x60length\x60/\x60count\x60 when no block is given.
- Never suppress exceptions or rescue bare \x60Exception\x60; rescue specific \x60StandardError\x60 subclasses.
- Enable \x60# frozen_string_literal: true\x60 at the top of Ruby files to avoid unnecessary string allocations.
"""
        },
        {
            "source_id": "rubocop_docs",
            "technology": "ecosystem",
            "version": "current",
            "topic": "performance",
            "doc_slug": "rubocop_rails_and_performance",
            "title": "RuboCop & RuboCop Rails Static Analysis Cops",
            "source_url": "https://docs.rubocop.org/rubocop-rails/",
            "authority": "ecosystem_official",
            "related_concepts": ["rubocop", "active_record", "callbacks", "find_each"],
            "markdown": """# RuboCop & RuboCop Rails Static Analysis

## Key RuboCop Rails and Performance Rules

> **Note/Warning:** Ecosystem tool documentation ([https://docs.rubocop.org/rubocop-rails/](https://docs.rubocop.org/rubocop-rails/)) — authority \x60ecosystem_official\x60.

- \x60Rails/FindEach\x60: Flags \x60Model.all.each\x60 or \x60where(...).each\x60 in favor of \x60find_each\x60 to avoid loading large tables into memory.
- \x60Rails/SkipsModelValidations\x60: Warns on methods like \x60update_column\x60, \x60update_all\x60, \x60toggle!\x60, and \x60increment!\x60 that bypass validations and callbacks (\x60after_save\x60, \x60after_commit\x60).
- \x60Rails/HasManyOrHasOneDependent\x60: Requires explicit \x60dependent: :destroy\x60, \x60:delete_all\x60, \x60:nullify\x60, or \x60:restrict_with_exception\x60 on associations.
"""
        },
        {
            "source_id": "rspec_docs",
            "technology": "ecosystem",
            "version": "current",
            "topic": "testing",
            "doc_slug": "rspec_rails_testing_guide",
            "title": "RSpec and rspec-rails Testing Conventions",
            "source_url": "https://rspec.info/documentation/",
            "authority": "ecosystem_official",
            "related_concepts": ["testing", "rspec", "transactions", "after_commit"],
            "markdown": """# RSpec and rspec-rails Testing Documentation

## Transactional Fixtures and Testing after_commit Callbacks in RSpec

> **Note/Warning:** Ecosystem testing documentation ([https://rspec.info/documentation/](https://rspec.info/documentation/)) — authority \x60ecosystem_official\x60.

- In \x60rspec-rails\x60 (with \x60use_transactional_fixtures = true\x60), each example runs inside a database transaction that rolls back at the end of the test.
- In Rails 5.0+ and 6.1+, Rails simulates transaction commit tracking inside test transactions so \x60after_commit\x60 callbacks fire automatically during transactional tests without requiring DatabaseCleaner truncation.
"""
        },
        {
            "source_id": "owasp_rails",
            "technology": "security",
            "version": "current",
            "topic": "security",
            "doc_slug": "owasp_ruby_on_rails_cheat_sheet",
            "title": "OWASP Ruby on Rails Security Cheat Sheet",
            "source_url": "https://cheatsheetseries.owasp.org/cheatsheets/Ruby_on_Rails_Cheat_Sheet.html",
            "authority": "security_standard",
            "related_concepts": ["security", "sql_injection", "csrf", "strong_parameters", "active_record"],
            "markdown": """# OWASP Ruby on Rails Security Cheat Sheet

## Preventing SQL Injection, Mass Assignment, CSRF, and XSS in Rails

> **Note/Warning:** External security standard ([https://cheatsheetseries.owasp.org/cheatsheets/Ruby_on_Rails_Cheat_Sheet.html](https://cheatsheetseries.owasp.org/cheatsheets/Ruby_on_Rails_Cheat_Sheet.html)) — authority \x60security_standard\x60.

1. **SQL Injection Prevention**: Never interpolate user input directly into SQL strings (\x60User.where("name = '#{params[:name]}'")\x60). Always use parameterized placeholders (\x60User.where("name = ?", params[:name])\x60) or hash conditions (\x60User.where(name: params[:name])\x60). Use \x60ActiveRecord::Base.sanitize_sql_like\x60 for \x60LIKE\x60 wildcards.
2. **Mass Assignment (Strong Parameters)**: Always filter controller parameters via \x60params.require(:model).permit(...)\x60 (or \x60params.expect(...)\x60 in Rails 8.0).
3. **CSRF Protection**: Keep \x60protect_from_forgery with: :exception\x60 enabled in \x60ApplicationController\x60 and validate OmniAuth state/CSRF tokens.
4. **Command Injection**: Never pass user strings to \x60eval\x60, \x60system("sh -c ...")\x60, backticks, or \x60Kernel.open\x60 (use \x60File.open\x60 and array arguments to \x60system("cmd", arg1)\x60).
"""
        },
    ]


def get_all_corpus_documents() -> List[Dict[str, Any]]:
    return (
        get_rails_corpus_documents()
        + get_ruby_corpus_documents()
        + get_ecosystem_and_security_documents()
    )


def get_curated_concepts_and_relationships() -> Dict[str, List[Dict[str, str]]]:
    """Return verified technical concepts and grounded directed relationships for the Knowledge Graph."""
    concepts = [
        {"id": "rails:after_commit", "name": "after_commit", "technology": "rails", "category": "callbacks", "description": "Active Record callback executed only after the outermost database transaction commits."},
        {"id": "rails:after_save", "name": "after_save", "technology": "rails", "category": "callbacks", "description": "Active Record callback executed after a record is saved, while still inside the open database transaction."},
        {"id": "rails:after_rollback", "name": "after_rollback", "technology": "rails", "category": "callbacks", "description": "Active Record callback executed when the surrounding database transaction rolls back."},
        {"id": "rails:callbacks", "name": "callbacks", "technology": "rails", "category": "active_record", "description": "Active Record lifecycle hooks triggered around state changes and database transactions."},
        {"id": "rails:active_record_callbacks", "name": "active_record_callbacks", "technology": "rails", "category": "active_record", "description": "Active Record Callbacks subsystem and lifecycle hook chain."},
        {"id": "rails:transactions", "name": "transactions", "technology": "rails", "category": "active_record", "description": "Atomic database transaction blocks managed by ActiveRecord::Base.transaction."},
        {"id": "rails:nested_transactions", "name": "nested_transactions", "technology": "rails", "category": "transactions", "description": "Nested transaction blocks joining parent transactions or creating SQL SAVEPOINTs via requires_new: true."},
        {"id": "rails:savepoints", "name": "savepoints", "technology": "rails", "category": "transactions", "description": "SQL SAVEPOINT sub-transactions created when transaction(requires_new: true) is used."},
        {"id": "rails:after_all_transactions_commit", "name": "after_all_transactions_commit", "technology": "rails", "category": "transactions", "description": "ActiveRecord.after_all_transactions_commit API introduced in Rails 7.2 to schedule post-commit hooks outside models."},
        {"id": "rails:includes", "name": "includes", "technology": "rails", "category": "queries", "description": "Eager loading method on ActiveRecord::Relation that delegates to preload or eager_load."},
        {"id": "rails:preload", "name": "preload", "technology": "rails", "category": "queries", "description": "Eager loading method that always loads associations in separate SQL queries."},
        {"id": "rails:eager_load", "name": "eager_load", "technology": "rails", "category": "queries", "description": "Eager loading method that always loads associations in a single LEFT OUTER JOIN query."},
        {"id": "rails:n_plus_one", "name": "n_plus_one", "technology": "rails", "category": "performance", "description": "N+1 query anti-pattern where 1 parent query triggers N lazy association queries."},
        {"id": "rails:strict_loading", "name": "strict_loading", "technology": "rails", "category": "queries", "description": "Active Record mode raising StrictLoadingViolationError when associations are lazily loaded."},
        {"id": "rails:n_plus_one_only", "name": "n_plus_one_only", "technology": "rails", "category": "queries", "description": "strict_loading mode (:n_plus_one_only) introduced in Rails 7.1 allowing single belongs_to loads."},
        {"id": "rails:associations", "name": "associations", "technology": "rails", "category": "active_record", "description": "Declarative relationships between Active Record models (belongs_to, has_many, has_one)."},
        {"id": "rails:dependent_destroy", "name": "dependent_destroy", "technology": "rails", "category": "associations", "description": "dependent: :destroy association option that instantiates child records and runs their destroy callbacks."},
        {"id": "rails:dependent_delete_all", "name": "dependent_delete_all", "technology": "rails", "category": "associations", "description": "dependent: :delete_all association option that deletes child rows directly in SQL without callbacks."},
        {"id": "rails:find_each", "name": "find_each", "technology": "rails", "category": "queries", "description": "ActiveRecord::Batches method yielding records in memory-bounded keyset-paginated batches of 1000."},
        {"id": "rails:in_batches", "name": "in_batches", "technology": "rails", "category": "queries", "description": "ActiveRecord::Batches method yielding relation batches for bulk SQL operations."},
        {"id": "rails:active_record", "name": "active_record", "technology": "rails", "category": "active_record", "description": "Rails ORM layer implementing the Active Record pattern."},
        {"id": "rails:connection_pool", "name": "connection_pool", "technology": "rails", "category": "performance", "description": "ActiveRecord::ConnectionAdapters::ConnectionPool managing thread-safe DB connection checkout."},
        {"id": "rails:zeitwerk", "name": "zeitwerk", "technology": "rails", "category": "autoloading", "description": "Thread-safe file-to-constant autoloader and eager loader used by Rails 6+."},
        {"id": "rails:classic_autoloader", "name": "classic_autoloader", "technology": "rails", "category": "autoloading", "description": "Legacy const_missing autoloader deprecated in Rails 6.1 and removed in Rails 7.0."},
        {"id": "rails:autoloading", "name": "autoloading", "technology": "rails", "category": "autoloading", "description": "Automatic constant loading and code reloading in Rails applications."},
        {"id": "rails:deprecations", "name": "deprecations", "technology": "rails", "category": "active_support", "description": "ActiveSupport::Deprecation instrumentation and lifecycle warnings."},
        {"id": "rails:active_support", "name": "active_support", "technology": "rails", "category": "active_support", "description": "Rails utility classes, core extensions, notifications, and deprecators."},
        {"id": "rails:active_job", "name": "active_job", "technology": "rails", "category": "active_job", "description": "Rails background job framework integrating with Sidekiq and Solid Queue."},
        {"id": "rails:load_async", "name": "load_async", "technology": "rails", "category": "queries", "description": "ActiveRecord::Relation#load_async background thread query execution introduced in Rails 7.0."},
        {"id": "rails:rails_6_1", "name": "rails_6_1", "technology": "rails", "category": "version", "description": "Ruby on Rails 6.1 release series."},
        {"id": "rails:rails_7_0", "name": "rails_7_0", "technology": "rails", "category": "version", "description": "Ruby on Rails 7.0 release series."},
        {"id": "rails:rails_7_1", "name": "rails_7_1", "technology": "rails", "category": "version", "description": "Ruby on Rails 7.1 release series."},
        {"id": "rails:rails_7_2", "name": "rails_7_2", "technology": "rails", "category": "version", "description": "Ruby on Rails 7.2 release series."},
        {"id": "rails:rails_8_0", "name": "rails_8_0", "technology": "rails", "category": "version", "description": "Ruby on Rails 8.0 release series."},
        {"id": "ruby:enumerable", "name": "enumerable", "technology": "ruby", "category": "enumerable", "description": "Ruby Enumerable mixin providing traversal, filtering, mapping, and aggregation over #each."},
        {"id": "ruby:enumerator", "name": "enumerator", "technology": "ruby", "category": "enumerable", "description": "External and lazy iteration wrapper class in Ruby."},
        {"id": "ruby:object_model", "name": "object_model", "technology": "ruby", "category": "object_model", "description": "Ruby class hierarchy (BasicObject -> Object -> Module -> Class) and ancestor method lookup."},
        {"id": "ruby:exceptions", "name": "exceptions", "technology": "ruby", "category": "exceptions", "description": "Ruby Exception and StandardError hierarchy."},
        {"id": "ruby:concurrency", "name": "concurrency", "technology": "ruby", "category": "concurrency", "description": "Ruby Thread, Fiber::Scheduler, and Ractor concurrency primitives."},
        {"id": "ruby:memory_management", "name": "memory_management", "technology": "ruby", "category": "memory_management", "description": "Ruby generational garbage collection (GC), heap compaction, and Variable Width Allocation."},
        {"id": "ruby:yjit", "name": "yjit", "technology": "ruby", "category": "memory_management", "description": "In-process Basic Block Versioning JIT compiler in CRuby 3.1+."},
    ]

    relationships = [
        # Examples explicitly highlighted in specification + comprehensive domain graph
        {"source": "rails:after_commit", "target": "rails:transactions", "type": "RELATED_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_callbacks.html", "notes": "after_commit executes only after the outermost database transaction commits."},
        {"source": "rails:after_commit", "target": "rails:transactions", "type": "DEPENDS_ON", "tech": "rails", "scope": "all", "url": "https://api.rubyonrails.org/v6.1/classes/ActiveRecord/Callbacks.html", "notes": "after_commit depends on transaction commit completion."},
        {"source": "rails:after_commit", "target": "rails:callbacks", "type": "PART_OF", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_callbacks.html", "notes": "after_commit is a transaction lifecycle hook in Active Record Callbacks."},
        {"source": "rails:after_commit", "target": "rails:active_record_callbacks", "type": "PART_OF", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_callbacks.html", "notes": "Part of ActiveRecord::Callbacks."},
        {"source": "rails:after_commit", "target": "rails:after_save", "type": "ALTERNATIVE_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_callbacks.html", "notes": "after_commit is used instead of after_save for external I/O and background jobs outside DB transactions."},
        {"source": "rails:after_commit", "target": "rails:after_rollback", "type": "RELATED_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_callbacks.html", "notes": "Complementary transaction completion callback on rollback."},
        {"source": "rails:after_commit", "target": "rails:active_job", "type": "RELATED_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_job_basics.html", "notes": "Background jobs should be enqueued after transaction commit to prevent RecordNotFound."},
        {"source": "rails:after_save", "target": "rails:callbacks", "type": "RELATED_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_callbacks.html", "notes": "after_save is a standard persistence callback."},
        {"source": "rails:after_save", "target": "rails:active_record_callbacks", "type": "PART_OF", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_callbacks.html", "notes": "Part of ActiveRecord::Callbacks."},
        {"source": "rails:after_all_transactions_commit", "target": "rails:rails_7_2", "type": "INTRODUCED_IN", "tech": "rails", "scope": "7.2", "url": "https://guides.rubyonrails.org/v7.2/active_record_callbacks.html", "notes": "ActiveRecord.after_all_transactions_commit was introduced in Rails 7.2."},
        {"source": "rails:after_all_transactions_commit", "target": "rails:after_commit", "type": "RELATED_TO", "tech": "rails", "scope": "7.2+", "url": "https://guides.rubyonrails.org/v7.2/active_record_callbacks.html", "notes": "Provides post-commit callback scheduling outside Active Record models."},
        {"source": "rails:includes", "target": "rails:preload", "type": "ALTERNATIVE_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_querying.html", "notes": "includes delegates to preload (separate queries) by default unless filtering on associated tables."},
        {"source": "rails:includes", "target": "rails:eager_load", "type": "ALTERNATIVE_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_querying.html", "notes": "includes switches to eager_load (LEFT OUTER JOIN) when filtering/ordering by associated tables."},
        {"source": "rails:preload", "target": "rails:eager_load", "type": "ALTERNATIVE_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_querying.html", "notes": "preload uses separate queries whereas eager_load uses a single LEFT OUTER JOIN."},
        {"source": "rails:includes", "target": "rails:n_plus_one", "type": "RELATED_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_querying.html", "notes": "Primary eager loading mechanism to eliminate N+1 queries."},
        {"source": "rails:eager_load", "target": "rails:associations", "type": "RELATED_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_querying.html", "notes": "Eagerly loads declared Active Record associations via LEFT OUTER JOIN."},
        {"source": "rails:strict_loading", "target": "rails:n_plus_one", "type": "RELATED_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/active_record_querying.html", "notes": "strict_loading raises StrictLoadingViolationError to prevent lazy N+1 queries."},
        {"source": "rails:strict_loading", "target": "rails:rails_6_1", "type": "INTRODUCED_IN", "tech": "rails", "scope": "6.1", "url": "https://guides.rubyonrails.org/v6.1/active_record_querying.html", "notes": "strict_loading was introduced in Rails 6.1."},
        {"source": "rails:n_plus_one_only", "target": "rails:rails_7_1", "type": "INTRODUCED_IN", "tech": "rails", "scope": "7.1", "url": "https://guides.rubyonrails.org/v7.1/active_record_querying.html", "notes": "strict_loading mode :n_plus_one_only was introduced in Rails 7.1."},
        {"source": "rails:n_plus_one_only", "target": "rails:strict_loading", "type": "PART_OF", "tech": "rails", "scope": "7.1+", "url": "https://guides.rubyonrails.org/v7.1/active_record_querying.html", "notes": "Configuration mode of strict_loading."},
        {"source": "rails:find_each", "target": "rails:in_batches", "type": "ALTERNATIVE_TO", "tech": "rails", "scope": "all", "url": "https://api.rubyonrails.org/v6.1/classes/ActiveRecord/Batches.html", "notes": "find_each yields model instances whereas in_batches yields Relation batches."},
        {"source": "rails:find_each", "target": "rails:active_record", "type": "PART_OF", "tech": "rails", "scope": "all", "url": "https://api.rubyonrails.org/v6.1/classes/ActiveRecord/Batches.html", "notes": "Provided by ActiveRecord::Batches."},
        {"source": "rails:nested_transactions", "target": "rails:transactions", "type": "PART_OF", "tech": "rails", "scope": "all", "url": "https://api.rubyonrails.org/v6.1/classes/ActiveRecord/Transactions/ClassMethods.html", "notes": "Nested transaction blocks within ActiveRecord::Base.transaction."},
        {"source": "rails:nested_transactions", "target": "rails:savepoints", "type": "DEPENDS_ON", "tech": "rails", "scope": "all", "url": "https://api.rubyonrails.org/v6.1/classes/ActiveRecord/Transactions/ClassMethods.html", "notes": "True isolated nested rollback requires SQL SAVEPOINTs via requires_new: true."},
        {"source": "rails:dependent_destroy", "target": "rails:dependent_delete_all", "type": "ALTERNATIVE_TO", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/association_basics.html", "notes": "dependent: :destroy runs model callbacks whereas dependent: :delete_all deletes directly in SQL."},
        {"source": "rails:dependent_destroy", "target": "rails:callbacks", "type": "DEPENDS_ON", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/association_basics.html", "notes": "Triggers before_destroy, after_destroy, and after_destroy_commit callbacks."},
        {"source": "rails:classic_autoloader", "target": "rails:rails_6_1", "type": "DEPRECATED_IN", "tech": "rails", "scope": "6.1", "url": "https://guides.rubyonrails.org/v6.1/autoloading_and_reloading_constants.html", "notes": "Classic autoloader was deprecated in Rails 6.1 and removed in Rails 7.0."},
        {"source": "rails:classic_autoloader", "target": "rails:zeitwerk", "type": "REPLACED_BY", "tech": "rails", "scope": "6.1+", "url": "https://guides.rubyonrails.org/v7.0/autoloading_and_reloading_constants.html", "notes": "Zeitwerk replaced the classic const_missing autoloader."},
        {"source": "rails:zeitwerk", "target": "rails:autoloading", "type": "PART_OF", "tech": "rails", "scope": "all", "url": "https://guides.rubyonrails.org/v6.1/autoloading_and_reloading_constants.html", "notes": "Zeitwerk powers Rails constant autoloading and eager loading."},
        {"source": "rails:connection_pool", "target": "rails:active_record", "type": "PART_OF", "tech": "rails", "scope": "all", "url": "https://api.rubyonrails.org/v6.1/classes/ActiveRecord/ConnectionAdapters/ConnectionPool.html", "notes": "Manages database connections per thread/fiber in Active Record."},
        {"source": "rails:load_async", "target": "rails:rails_7_0", "type": "INTRODUCED_IN", "tech": "rails", "scope": "7.0", "url": "https://guides.rubyonrails.org/v7.0/active_record_querying.html", "notes": "Relation#load_async was introduced in Rails 7.0."},
        {"source": "rails:load_async", "target": "rails:connection_pool", "type": "DEPENDS_ON", "tech": "rails", "scope": "7.0+", "url": "https://guides.rubyonrails.org/v7.0/active_record_querying.html", "notes": "Background async queries lease connections from the Active Record ConnectionPool."},
        {"source": "rails:deprecations", "target": "rails:active_support", "type": "PART_OF", "tech": "rails", "scope": "all", "url": "https://api.rubyonrails.org/v7.2/classes/ActiveSupport/Deprecation.html", "notes": "Implemented via ActiveSupport::Deprecation and Rails.application.deprecators."},
        {"source": "ruby:enumerable", "target": "ruby:enumerator", "type": "RELATED_TO", "tech": "ruby", "scope": "all", "url": "https://docs.ruby-lang.org/en/3.3/Enumerable.html", "notes": "Enumerable methods return an Enumerator when called without a block; #lazy returns Enumerator::Lazy."},
        {"source": "ruby:yjit", "target": "ruby:memory_management", "type": "RELATED_TO", "tech": "ruby", "scope": "all", "url": "https://docs.ruby-lang.org/en/3.3/GC.html", "notes": "YJIT coordinates with Ruby GC and code page allocation."},
    ]

    return {"concepts": concepts, "relationships": relationships}
