package com.ideaecho.app.data

import android.content.Context
import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName="ideas")
data class IdeaEntity(
    @PrimaryKey val id: String,
    val text: String,
    val recordedAt: String,
    val imagesJson: String,
    val owner: String? = null,
    val rawVersion: Int = 0,
    val revision: Long = 1,
    val syncedRevision: Long = 0,
    val syncError: String? = null,
    val pendingMutation: String? = null,
    val pendingPayload: String? = null,
    val pendingRevision: Long? = null
)

@Entity(tableName="drafts")
data class DraftEntity(@PrimaryKey val key: Int = 1, val text: String, val imagesJson: String, val saveId: String)

@Entity(tableName="uploaded_images",primaryKeys=["accountId","imageId"])
data class UploadedImage(val accountId: String,val imageId: String,val sha256: String)

@Dao
interface IdeaDao {
    @Query("SELECT * FROM ideas ORDER BY recordedAt DESC") suspend fun all(): List<IdeaEntity>
    @Query("SELECT * FROM ideas ORDER BY recordedAt DESC") fun observeAll(): Flow<List<IdeaEntity>>
    @Query("SELECT * FROM ideas WHERE id=:id") suspend fun find(id: String): IdeaEntity?
    @Insert(onConflict=OnConflictStrategy.IGNORE) suspend fun insert(idea: IdeaEntity): Long
    @Update suspend fun update(idea: IdeaEntity)
    @Query("SELECT * FROM drafts WHERE `key`=1") suspend fun draft(): DraftEntity?
    @Insert(onConflict=OnConflictStrategy.REPLACE) suspend fun setDraft(draft: DraftEntity)
    @Query("SELECT * FROM drafts WHERE `key`=1") fun observeDraft(): Flow<DraftEntity?>
    @Query("DELETE FROM drafts WHERE `key`=1 AND saveId=:saveId") suspend fun clearDraft(saveId: String)
    @Query("SELECT * FROM uploaded_images WHERE accountId=:owner AND imageId=:id") suspend fun uploaded(owner: String,id: String): UploadedImage?
    @Insert(onConflict=OnConflictStrategy.REPLACE) suspend fun markImageUploaded(image: UploadedImage)
}

@Database(entities=[IdeaEntity::class,DraftEntity::class,UploadedImage::class],version=1,exportSchema=true)
abstract class AppDatabase : RoomDatabase() {
    abstract fun dao(): IdeaDao
    companion object {
        @Volatile private var instance: AppDatabase? = null
        fun get(context: Context): AppDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(context.applicationContext,AppDatabase::class.java,"idea-echo.db").build().also { instance=it }
        }
    }
}
