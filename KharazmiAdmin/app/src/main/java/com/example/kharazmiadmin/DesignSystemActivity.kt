package com.example.kharazmiadmin

import android.os.Bundle
import android.widget.ImageView

class DesignSystemActivity : BaseActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_design_system)

        // تولید و بایند آواتارهای فرضی جهت عیب‌یابی طراح
        val avatar1 = findViewById<ImageView>(R.id.imgAvatarSample1)
        val avatar2 = findViewById<ImageView>(R.id.imgAvatarSample2)
        val avatar3 = findViewById<ImageView>(R.id.imgAvatarSample3)

        avatar1?.setImageDrawable(AvatarHelper.getAvatar(this, "الارا صیامی", 101))
        avatar2?.setImageDrawable(AvatarHelper.getAvatar(this, "سهراب سپهری", 102))
        avatar3?.setImageDrawable(AvatarHelper.getAvatar(this, "فخرالنسا پوریافرانی", 103))
    }
}
