// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteTransactionListener
import android.os.CancellationSignal
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.sqlite.db.SupportSQLiteOpenHelper
import androidx.sqlite.db.SupportSQLiteProgram
import androidx.sqlite.db.SupportSQLiteQuery
import androidx.sqlite.db.SupportSQLiteStatement
import java.util.Locale
import org.sqlite.database.sqlite.SQLiteDatabase as NgaDatabase
import org.sqlite.database.sqlite.SQLiteOpenHelper as NgaOpenHelper
import org.sqlite.database.sqlite.SQLiteStatement as NgaStatement
import org.sqlite.database.sqlite.SQLiteTransactionListener as NgaTransactionListener

class NgaSQLiteOpenHelperFactory : SupportSQLiteOpenHelper.Factory {
    companion object {
        init {
            System.loadLibrary("sqliteX")
        }
    }

    override fun create(
        configuration: SupportSQLiteOpenHelper.Configuration,
    ): SupportSQLiteOpenHelper {
        val helper = BridgedHelper(
            configuration.context,
            configuration.name,
            configuration.callback,
        )
        return NgaSQLiteOpenHelper(helper)
    }
}

private class BridgedHelper(
    context: Context,
    name: String?,
    private val callback: SupportSQLiteOpenHelper.Callback,
) : NgaOpenHelper(context, name, null, callback.version) {
    override fun onConfigure(db: NgaDatabase) {
        callback.onConfigure(NgaSQLiteDatabase(db))
    }

    override fun onCreate(db: NgaDatabase) {
        callback.onCreate(NgaSQLiteDatabase(db))
    }

    override fun onUpgrade(db: NgaDatabase, oldVersion: Int, newVersion: Int) {
        callback.onUpgrade(NgaSQLiteDatabase(db), oldVersion, newVersion)
    }

    override fun onDowngrade(db: NgaDatabase, oldVersion: Int, newVersion: Int) {
        callback.onDowngrade(NgaSQLiteDatabase(db), oldVersion, newVersion)
    }

    override fun onOpen(db: NgaDatabase) {
        callback.onOpen(NgaSQLiteDatabase(db))
    }
}

private class NgaSQLiteOpenHelper(
    private val delegate: BridgedHelper,
) : SupportSQLiteOpenHelper {
    override val databaseName: String?
        get() = delegate.databaseName

    override fun setWriteAheadLoggingEnabled(enabled: Boolean) {
        delegate.setWriteAheadLoggingEnabled(enabled)
    }

    override val writableDatabase: SupportSQLiteDatabase
        get() = NgaSQLiteDatabase(delegate.writableDatabase)

    override val readableDatabase: SupportSQLiteDatabase
        get() = NgaSQLiteDatabase(delegate.readableDatabase)

    override fun close() {
        delegate.close()
    }
}

private class NgaTransactionAdapter(
    private val delegate: SQLiteTransactionListener,
) : NgaTransactionListener {
    override fun onBegin() {
        delegate.onBegin()
    }

    override fun onCommit() {
        delegate.onCommit()
    }

    override fun onRollback() {
        delegate.onRollback()
    }
}

internal class NgaSQLiteDatabase(
    private val delegate: NgaDatabase,
) : SupportSQLiteDatabase {
    override fun compileStatement(sql: String): SupportSQLiteStatement =
        NgaSQLiteStatement(delegate.compileStatement(sql))

    override fun beginTransaction() {
        delegate.beginTransaction()
    }

    override fun beginTransactionNonExclusive() {
        delegate.beginTransactionNonExclusive()
    }

    override fun beginTransactionWithListener(
        transactionListener: SQLiteTransactionListener,
    ) {
        delegate.beginTransactionWithListener(
            NgaTransactionAdapter(transactionListener),
        )
    }

    override fun beginTransactionWithListenerNonExclusive(
        transactionListener: SQLiteTransactionListener,
    ) {
        delegate.beginTransactionWithListenerNonExclusive(
            NgaTransactionAdapter(transactionListener),
        )
    }

    override fun endTransaction() {
        delegate.endTransaction()
    }

    override fun setTransactionSuccessful() {
        delegate.setTransactionSuccessful()
    }

    override fun inTransaction(): Boolean = delegate.inTransaction()

    override val isDbLockedByCurrentThread: Boolean
        get() = delegate.isDbLockedByCurrentThread

    override fun yieldIfContendedSafely(): Boolean =
        delegate.yieldIfContendedSafely()

    override fun yieldIfContendedSafely(
        sleepAfterYieldDelayMillis: Long,
    ): Boolean = delegate.yieldIfContendedSafely(sleepAfterYieldDelayMillis)

    override fun query(query: String): Cursor =
        delegate.rawQuery(query, null)

    override fun query(query: String, bindArgs: Array<out Any?>): Cursor =
        delegate.rawQuery(query, bindArgs.toStringArray())

    override fun query(query: SupportSQLiteQuery): Cursor =
        query(query, null)

    override fun query(
        query: SupportSQLiteQuery,
        cancellationSignal: CancellationSignal?,
    ): Cursor {
        val args = stringArgs(query)
        return if (cancellationSignal == null) {
            delegate.rawQuery(query.sql, args)
        } else {
            delegate.rawQuery(query.sql, args, cancellationSignal)
        }
    }

    override fun insert(
        table: String,
        conflictAlgorithm: Int,
        values: ContentValues,
    ): Long = delegate.insertWithOnConflict(table, null, values, conflictAlgorithm)

    override fun delete(
        table: String,
        whereClause: String?,
        whereArgs: Array<out Any?>?,
    ): Int = delegate.delete(table, whereClause, whereArgs.toStringArray())

    override fun update(
        table: String,
        conflictAlgorithm: Int,
        values: ContentValues,
        whereClause: String?,
        whereArgs: Array<out Any?>?,
    ): Int = delegate.updateWithOnConflict(
        table,
        values,
        whereClause,
        whereArgs.toStringArray(),
        conflictAlgorithm,
    )

    override fun execSQL(sql: String) {
        delegate.execSQL(sql)
    }

    override fun execSQL(sql: String, bindArgs: Array<out Any?>) {
        delegate.execSQL(sql, bindArgs)
    }

    override val isReadOnly: Boolean
        get() = delegate.isReadOnly

    override val isOpen: Boolean
        get() = delegate.isOpen

    override fun needUpgrade(newVersion: Int): Boolean =
        delegate.needUpgrade(newVersion)

    override val path: String?
        get() = delegate.path

    override fun setLocale(locale: Locale) {
        delegate.setLocale(locale)
    }

    override fun setMaxSqlCacheSize(cacheSize: Int) {
        delegate.setMaxSqlCacheSize(cacheSize)
    }

    override fun setForeignKeyConstraintsEnabled(enable: Boolean) {
        delegate.setForeignKeyConstraintsEnabled(enable)
    }

    override fun enableWriteAheadLogging(): Boolean =
        delegate.enableWriteAheadLogging()

    override fun disableWriteAheadLogging() {
        delegate.disableWriteAheadLogging()
    }

    override val isWriteAheadLoggingEnabled: Boolean
        get() = delegate.isWriteAheadLoggingEnabled

    override val attachedDbs: List<android.util.Pair<String, String>>?
        get() = delegate.attachedDbs

    override val isDatabaseIntegrityOk: Boolean
        get() = delegate.isDatabaseIntegrityOk

    override var version: Int
        get() = delegate.version
        set(value) {
            delegate.version = value
        }

    override var pageSize: Long
        get() = delegate.pageSize
        set(value) {
            delegate.setPageSize(value)
        }

    override val maximumSize: Long
        get() = delegate.maximumSize

    override fun setMaximumSize(numBytes: Long): Long =
        delegate.setMaximumSize(numBytes)

    override fun close() {
        delegate.close()
    }

    private fun stringArgs(query: SupportSQLiteQuery): Array<String?>? {
        val recorder = RecordingProgram()
        query.bindTo(recorder)
        if (recorder.args.isEmpty()) return null
        val maxIndex = recorder.args.keys.max()
        return Array(maxIndex) { i -> recorder.args[i + 1]?.toString() }
    }

    private fun Array<out Any?>?.toStringArray(): Array<String?>? =
        this?.map { it?.toString() }?.toTypedArray()
}

private class RecordingProgram : SupportSQLiteProgram {
    val args = mutableMapOf<Int, Any?>()

    override fun bindNull(index: Int) {
        args[index] = null
    }

    override fun bindLong(index: Int, value: Long) {
        args[index] = value
    }

    override fun bindDouble(index: Int, value: Double) {
        args[index] = value
    }

    override fun bindString(index: Int, value: String) {
        args[index] = value
    }

    override fun bindBlob(index: Int, value: ByteArray) {
        args[index] = value
    }

    override fun clearBindings() {
        args.clear()
    }

    override fun close() {
    }
}

internal class NgaSQLiteStatement(
    private val delegate: NgaStatement,
) : SupportSQLiteStatement {
    override fun execute() {
        delegate.execute()
    }

    override fun executeUpdateDelete(): Int = delegate.executeUpdateDelete()

    override fun executeInsert(): Long = delegate.executeInsert()

    override fun simpleQueryForLong(): Long = delegate.simpleQueryForLong()

    override fun simpleQueryForString(): String? = delegate.simpleQueryForString()

    override fun bindNull(index: Int) {
        delegate.bindNull(index)
    }

    override fun bindLong(index: Int, value: Long) {
        delegate.bindLong(index, value)
    }

    override fun bindDouble(index: Int, value: Double) {
        delegate.bindDouble(index, value)
    }

    override fun bindString(index: Int, value: String) {
        delegate.bindString(index, value)
    }

    override fun bindBlob(index: Int, value: ByteArray) {
        delegate.bindBlob(index, value)
    }

    override fun clearBindings() {
        delegate.clearBindings()
    }

    override fun close() {
        delegate.close()
    }
}
